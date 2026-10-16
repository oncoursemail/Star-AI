// RAMForge kernel_lab: frozen-reference harness for CPU matmul kernel variants (AlphaEvolve-style loop, step 0).
//
// What it does
//   * builds deterministic inputs in the exact formats the live decode path uses on this CPU:
//       - repacked Q4_K expert/dense weights (block_q4_Kx8, 8 rows interleaved) x Q8_K activation  -> ggml_gemv_q4_K_8x8_q8_K
//       - Q8_0 weights x Q8_0 activation (one row at a time)                                      -> ggml_vec_dot_q8_0_q8_0
//   * computes the REFERENCE with ggml's portable *_generic C kernels (never the code under test) and keeps it
//     in memory the candidate cannot reach (copied before the candidate runs, inputs re-checked afterwards).
//   * runs each candidate (the shipped AVX2 kernel, plus any variant linked in as rf_candidate_*), checks the
//     result against the reference with a tolerance derived from the shipped kernel's own error, and times it:
//       hot  = weights resident in L2/L3 (compute ceiling of one core)
//       cold = weights streamed from DRAM local to the pinned core (what decode sees)
//       node = all physical cores of one node streaming their own slices (does one node's compute keep up with
//              its single memory channel?)
// Build (on the server, against the RAMForge build):
//   gcc -O3 -march=native -pthread kernel_lab.c [cand.c -DRF_HAVE_CAND] -I$SRC/ggml/include \
//       -L$BIN -lggml-cpu -lggml-base -Wl,-rpath,$BIN -o kernel_lab
// Run: kernel_lab [cpu_node] [hot]
#define _GNU_SOURCE
#include <math.h>
#include <pthread.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "ggml.h"
#include "ggml-cpu.h"

typedef void (*gemv_fn)(int n, float * s, size_t bs, const void * vx, const void * vy, int nr, int nc);
void ggml_gemv_q4_K_8x8_q8_K(int n, float * s, size_t bs, const void * vx, const void * vy, int nr, int nc);
void ggml_gemv_q4_K_8x8_q8_K_generic(int n, float * s, size_t bs, const void * vx, const void * vy, int nr, int nc);
void ggml_vec_dot_q8_0_q8_0(int n, float * s, size_t bs, const void * vx, size_t bx, const void * vy, size_t by, int nrc);
void ggml_vec_dot_q8_0_q8_0_generic(int n, float * s, size_t bs, const void * vx, size_t bx, const void * vy, size_t by, int nrc);
void quantize_row_q8_K(const float * x, void * y, int64_t k);
void quantize_row_q8_0(const float * x, void * y, int64_t k);
#ifdef RF_HAVE_CAND
void rf_candidate_gemv_q4_K_8x8(int n, float * s, size_t bs, const void * vx, const void * vy, int nr, int nc);
#endif

#define K 2048                       // n_embd of Qwen3.6-35B-A3B (expert gate/up input width)
#define Q4KX8_BYTES 1152             // block_q4_Kx8: 8 x (d, dmin) fp16 + 96 scale bytes + 1024 quant bytes
#define Q8K_BYTES 292                // block_q8_K: float d + 256 int8 + 16 int16 bsums
#define Q80_BYTES 34                 // block_q8_0: fp16 d + 32 int8

static uint64_t rng = 0x9E3779B97F4A7C15ull;
static uint32_t rnd(void) { rng ^= rng << 13; rng ^= rng >> 7; rng ^= rng << 17; return (uint32_t) (rng >> 11); }
static float frnd(void) { return (rnd() % 20001) / 10000.0f - 1.0f; }
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }

static void pin(int cpu) { cpu_set_t c; CPU_ZERO(&c); CPU_SET(cpu, &c); pthread_setaffinity_np(pthread_self(), sizeof c, &c); }

static int node_cpus[64], node_ncpu = 0, hot_only = 0;
static void read_node(int node) {
    char p[96]; snprintf(p, sizeof p, "/sys/devices/system/node/node%d/cpulist", node);
    FILE * f = fopen(p, "r"); char b[512] = {0}; if (f) { if (!fgets(b, sizeof b, f)) b[0] = 0; fclose(f); }
    for (char * s = strtok(b, ",\n"); s; s = strtok(NULL, ",\n")) {
        int a, z; if (sscanf(s, "%d-%d", &a, &z) == 2) { for (int c = a; c <= z; c++) node_cpus[node_ncpu++] = c; }
        else node_cpus[node_ncpu++] = atoi(s);
    }
}

static void fill_q4kx8(uint8_t * w, size_t nblk) {
    for (size_t b = 0; b < nblk; b++) {
        uint8_t * blk = w + b * Q4KX8_BYTES;
        ggml_fp16_t * h = (ggml_fp16_t *) blk;
        for (int i = 0; i < 8; i++) { h[i] = ggml_fp32_to_fp16(0.002f + 0.01f * (rnd() % 100) / 100.0f); h[8 + i] = ggml_fp32_to_fp16(0.001f * (rnd() % 100) / 100.0f); }
        for (int i = 32; i < Q4KX8_BYTES; i++) blk[i] = (uint8_t) rnd();
    }
}
static void fill_q80(uint8_t * w, size_t nblk) {
    for (size_t b = 0; b < nblk; b++) {
        uint8_t * blk = w + b * Q80_BYTES;
        *(ggml_fp16_t *) blk = ggml_fp32_to_fp16(0.001f + 0.01f * (rnd() % 100) / 100.0f);
        for (int i = 2; i < Q80_BYTES; i++) blk[i] = (uint8_t) rnd();
    }
}

static double max_rel(const float * a, const float * ref, int n) {
    double scale = 0, err = 0;
    for (int i = 0; i < n; i++) { scale = fmax(scale, fabs(ref[i])); }
    for (int i = 0; i < n; i++) { err = fmax(err, fabs(a[i] - ref[i])); }
    return scale > 0 ? err / scale : err;
}

// ---- Q4_K x8 gemv ----
static double time_gemv(gemv_fn f, const uint8_t * w, size_t rows, const void * act, float * out, double min_s) {
    size_t bytes = rows / 8 * (K / 256) * Q4KX8_BYTES, done = 0; double t0 = now(), t;
    do { f(K, out, rows, w, act, 1, (int) rows); done += bytes; t = now(); } while (t - t0 < min_s);
    return done / (t - t0) / 1e9;
}

typedef struct { gemv_fn f; int cpu; size_t rows; const void * act; double gbps; pthread_barrier_t * bar; } nodejob;
static void * node_worker(void * p) {
    nodejob * j = p; pin(j->cpu);
    size_t bytes = j->rows / 8 * (K / 256) * Q4KX8_BYTES;
    uint8_t * w = aligned_alloc(64, bytes); fill_q4kx8(w, j->rows / 8 * (K / 256));   // first touch: local to this core's node
    float * out = aligned_alloc(64, j->rows * sizeof(float));
    pthread_barrier_wait(j->bar);
    j->gbps = time_gemv(j->f, w, j->rows, j->act, out, 3.0);
    free(w); free(out); return NULL;
}

static void bench_q4k(const char * name, gemv_fn f, double tol, const uint8_t * w_hot, size_t rows_hot, const void * act,
                      const float * ref, int cpu0) {
    float * out = aligned_alloc(64, rows_hot * sizeof(float));
    uint8_t * guard = malloc(rows_hot / 8 * (K / 256) * Q4KX8_BYTES); memcpy(guard, w_hot, rows_hot / 8 * (K / 256) * Q4KX8_BYTES);
    memset(out, 0, rows_hot * sizeof(float));
    f(K, out, rows_hot, w_hot, act, 1, (int) rows_hot);
    double err = max_rel(out, ref, (int) rows_hot);
    int inputs_ok = memcmp(guard, w_hot, rows_hot / 8 * (K / 256) * Q4KX8_BYTES) == 0;
    int ok = err <= tol && inputs_ok;
    double hot = time_gemv(f, w_hot, rows_hot, act, out, 2.0);
    if (hot_only) {
        printf("{\"kernel\":\"q4_K_8x8 gemv\",\"variant\":\"%s\",\"correct\":%s,\"max_rel_err\":%.3g,\"tol\":%.3g,\"inputs_untouched\":%s,\"hot_gbps_1core\":%.2f}\n",
               name, ok ? "true" : "false", err, tol, inputs_ok ? "true" : "false", hot);
        free(out); free(guard); return;
    }
    size_t rows_cold = 1u << 18;    // 262144 rows x 2048 = 302 MB of weights, far beyond L3
    uint8_t * wc = aligned_alloc(64, rows_cold / 8 * (K / 256) * Q4KX8_BYTES); fill_q4kx8(wc, rows_cold / 8 * (K / 256));
    float * oc = aligned_alloc(64, rows_cold * sizeof(float));
    double cold = time_gemv(f, wc, rows_cold, act, oc, 3.0);
    free(wc); free(oc);
    // one node: every physical core streams its own local slice at once
    int ncores = node_ncpu / 2; nodejob jobs[32]; pthread_t th[32]; pthread_barrier_t bar; pthread_barrier_init(&bar, NULL, ncores);
    for (int i = 0; i < ncores; i++) { jobs[i] = (nodejob){f, node_cpus[i], 1u << 17, act, 0, &bar}; pthread_create(&th[i], NULL, node_worker, &jobs[i]); }
    double node = 0; for (int i = 0; i < ncores; i++) { pthread_join(th[i], NULL); node += jobs[i].gbps; }
    printf("{\"kernel\":\"q4_K_8x8 gemv\",\"variant\":\"%s\",\"correct\":%s,\"max_rel_err\":%.3g,\"tol\":%.3g,\"inputs_untouched\":%s,"
           "\"hot_gbps_1core\":%.2f,\"cold_gbps_1core\":%.2f,\"node_gbps_%dcores\":%.2f}\n",
           name, ok ? "true" : "false", err, tol, inputs_ok ? "true" : "false", hot, cold, ncores, node);
    (void) cpu0; free(out); free(guard);
}

// ---- Q8_0 row dots (the dense attention / delta-net / shared-expert tensors are Q8_0) ----
static void bench_q80(const char * name, int generic, int cpu0) {
    size_t rows = 1u << 17, rb = (K / 32) * Q80_BYTES;            // 131072 rows x 2176 B = 285 MB
    uint8_t * w = aligned_alloc(64, rows * rb); fill_q80(w, rows * (K / 32));
    float x[K]; for (int i = 0; i < K; i++) x[i] = frnd();
    uint8_t act[(K / 32) * Q80_BYTES]; quantize_row_q8_0(x, act, K);
    float s; size_t hot_rows = 128; double t0, t; size_t done;
    done = 0; t0 = now();
    do { for (size_t r = 0; r < hot_rows; r++) (generic ? ggml_vec_dot_q8_0_q8_0_generic : ggml_vec_dot_q8_0_q8_0)(K, &s, 0, w + r * rb, 0, act, 0, 1); done += hot_rows * rb; t = now(); } while (t - t0 < 2.0);
    double hot = done / (t - t0) / 1e9;
    done = 0; t0 = now();
    do { for (size_t r = 0; r < rows; r++) (generic ? ggml_vec_dot_q8_0_q8_0_generic : ggml_vec_dot_q8_0_q8_0)(K, &s, 0, w + r * rb, 0, act, 0, 1); done += rows * rb; t = now(); } while (t - t0 < 3.0);
    double cold = done / (t - t0) / 1e9;
    printf("{\"kernel\":\"q8_0 vec_dot\",\"variant\":\"%s\",\"hot_gbps_1core\":%.2f,\"cold_gbps_1core\":%.2f}\n", name, hot, cold);
    (void) cpu0; free(w);
}

int main(int argc, char ** argv) {
    int node = argc > 1 ? atoi(argv[1]) : 0;
    hot_only = argc > 2 && !strcmp(argv[2], "hot");   // hot: no DRAM streaming (safe while the brain is busy)
    read_node(node); pin(node_cpus[0]);
    ggml_cpu_init();
    const size_t rows_hot = 256;      // 256 rows x 2048 Q4_K = 295 KB: stays in L2 (512 KB) / L3
    uint8_t * w = aligned_alloc(64, rows_hot / 8 * (K / 256) * Q4KX8_BYTES); fill_q4kx8(w, rows_hot / 8 * (K / 256));
    float x[K]; for (int i = 0; i < K; i++) x[i] = frnd();
    uint8_t * act = aligned_alloc(64, (K / 256) * Q8K_BYTES); quantize_row_q8_K(x, act, K);
    float * ref = aligned_alloc(64, rows_hot * sizeof(float));
    ggml_gemv_q4_K_8x8_q8_K_generic(K, ref, rows_hot, w, act, 1, (int) rows_hot);   // frozen reference
    // tolerance: the shipped AVX2 kernel's own deviation from the generic reference, x4, floor 1e-5
    float * tmp = aligned_alloc(64, rows_hot * sizeof(float)); ggml_gemv_q4_K_8x8_q8_K(K, tmp, rows_hot, w, act, 1, (int) rows_hot);
    double tol = fmax(1e-5, 4 * max_rel(tmp, ref, (int) rows_hot));
    printf("{\"node\":%d,\"cpu\":%d,\"shipped_vs_generic_rel_err\":%.3g}\n", node, node_cpus[0], max_rel(tmp, ref, (int) rows_hot));
    bench_q4k("generic C (reference)", ggml_gemv_q4_K_8x8_q8_K_generic, tol, w, rows_hot, act, ref, node_cpus[0]);
    bench_q4k("shipped AVX2", ggml_gemv_q4_K_8x8_q8_K, tol, w, rows_hot, act, ref, node_cpus[0]);
#ifdef RF_HAVE_CAND
    bench_q4k("candidate", rf_candidate_gemv_q4_K_8x8, tol, w, rows_hot, act, ref, node_cpus[0]);
#endif
    if (!hot_only) bench_q80("shipped AVX2", 0, node_cpus[0]);
    return 0;
}
