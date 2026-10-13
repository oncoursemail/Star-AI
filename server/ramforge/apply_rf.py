#!/usr/bin/env python3
"""RAMForge ExpertFlow prototype patch for llama.cpp b11541 (commit f2918cabb).

Usage: python3 apply_rf.py <llama.cpp source dir>

Two opt-in changes, both OFF unless their environment variable is set at run time:
  GGML_NUMA_BLOCK=1       with --numa distribute, compute thread ith runs on node ith*N/nth (block mapping)
                          instead of node ith % N (round-robin).
  LLAMA_RAMFORGE_PLACE=1  after the weights are loaded, bind the rows each node's threads read in the
                          decode matmul kernels to that node (mbind MPOL_BIND + MPOL_MF_MOVE), per expert
                          slice for 3-D expert tensors. LLAMA_RAMFORGE_NTH (default 24) = generation threads.
A binary built with this patch behaves exactly like the unpatched one when neither variable is set.
"""
import sys

root = sys.argv[1]


def sub(path, old, new, count=1):
    p = f"{root}/{path}"
    s = open(p).read()
    if old not in s:
        sys.exit(f"pattern not found in {path}: {old[:70]!r}")
    s = s.replace(old, new, count)
    open(p, "w").write(s)


# 1) ggml-cpu.c: optional block thread->node mapping
c = "ggml/src/ggml-cpu/ggml-cpu.c"
sub(c, "static void set_numa_thread_affinity(int thread_n) {\n    if (!ggml_is_numa()) {",
    "static int ramforge_numa_block = -1; // RAMForge: GGML_NUMA_BLOCK=1 -> threads [k*n/N, (k+1)*n/N) on node k\n\n"
    "static void set_numa_thread_affinity(int thread_n, int n_threads) {\n    if (!ggml_is_numa()) {")
sub(c, "            node_num = thread_n % g_state.numa.n_nodes;\n",
    "            if (ramforge_numa_block < 0) {\n"
    "                const char * e = getenv(\"GGML_NUMA_BLOCK\");\n"
    "                ramforge_numa_block = (e && atoi(e) > 0) ? 1 : 0;\n"
    "            }\n"
    "            if (ramforge_numa_block && n_threads > 0) {\n"
    "                node_num = (int) (((int64_t) thread_n * g_state.numa.n_nodes) / n_threads);\n"
    "                if (node_num >= (int) g_state.numa.n_nodes) node_num = g_state.numa.n_nodes - 1;\n"
    "            } else {\n"
    "                node_num = thread_n % g_state.numa.n_nodes;\n"
    "            }\n")
sub(c, "static void set_numa_thread_affinity(int thread_n) { UNUSED(thread_n);  }",
    "static void set_numa_thread_affinity(int thread_n, int n_threads) { UNUSED(thread_n); UNUSED(n_threads); }")
sub(c, "    set_numa_thread_affinity(state->ith);\n#endif",
    "    set_numa_thread_affinity(state->ith, atomic_load_explicit(&tp->n_graph, memory_order_relaxed) & GGML_THREADPOOL_N_THREADS_MASK);\n#endif")

# 1b) ggml-cpu.c: optional per-op wall-time profile (GGML_RF_PROFILE=<file>), thread 0 only, cheap.
#     For each graph node: compute time of thread 0 and time until the barrier released (= slowest thread).
#     Keyed by op and, for MUL_MAT / MUL_MAT_ID, src0 type. Separate tables per thread count (24 = decode,
#     48 = prompt batches with -t 24 -tb 48). The file is rewritten every 64 graphs.
PROF = r'''
// ---- RAMForge op profiler (GGML_RF_PROFILE=<file>) ----
#define RF_MAXK (GGML_OP_COUNT * 64)
#define RF_NTH 2
static int rf_prof_on = -1;
static const char * rf_prof_path = NULL;
static double rf_compute[RF_NTH][RF_MAXK], rf_wall[RF_NTH][RF_MAXK];
static int64_t rf_count[RF_NTH][RF_MAXK], rf_graphs[RF_NTH], rf_nodes[RF_NTH];
static double rf_graph_s[RF_NTH];
static int rf_nth_of[RF_NTH] = {0, 0};
static double rf_now(void) { struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return ts.tv_sec + ts.tv_nsec * 1e-9; }
static int rf_slot(int nth) {
    for (int i = 0; i < RF_NTH; i++) { if (rf_nth_of[i] == nth) return i; if (rf_nth_of[i] == 0) { rf_nth_of[i] = nth; return i; } }
    return -1;
}
static void rf_dump(void) {
    FILE * f = fopen(rf_prof_path, "w");
    if (!f) return;
    for (int s = 0; s < RF_NTH; s++) {
        if (!rf_nth_of[s]) continue;
        fprintf(f, "# nth=%d graphs=%lld nodes=%lld graph_wall_s=%.3f\n", rf_nth_of[s], (long long) rf_graphs[s], (long long) rf_nodes[s], rf_graph_s[s]);
        for (int k = 0; k < RF_MAXK; k++) {
            if (!rf_count[s][k]) continue;
            const int op = k / 64, ty = k % 64;
            fprintf(f, "nth=%d\t%s\t%s\tcount=%lld\tcompute_s=%.4f\twall_s=%.4f\n", rf_nth_of[s], ggml_op_name((enum ggml_op) op),
                    (op == GGML_OP_MUL_MAT || op == GGML_OP_MUL_MAT_ID) ? ggml_type_name((enum ggml_type) ty) : "-",
                    (long long) rf_count[s][k], rf_compute[s][k], rf_wall[s][k]);
        }
    }
    fclose(f);
}
'''
sub(c, "static int ramforge_numa_block = -1;", PROF + "\nstatic int ramforge_numa_block = -1;")
sub(c, "    for (int node_n = 0; node_n < cgraph->n_nodes && atomic_load_explicit(&tp->abort, memory_order_relaxed) != node_n; node_n++) {\n"
       "        struct ggml_tensor * node = cgraph->nodes[node_n];\n",
    "    if (rf_prof_on < 0) { rf_prof_path = getenv(\"GGML_RF_PROFILE\"); rf_prof_on = rf_prof_path ? 1 : 0; }\n"
    "    const int rf_s = (rf_prof_on && state->ith == 0) ? rf_slot(params.nth) : -1;\n"
    "    const double rf_g0 = rf_s >= 0 ? rf_now() : 0.0;\n"
    "    double rf_t0 = rf_g0, rf_t1 = 0.0; int rf_k = 0;\n"
    "    for (int node_n = 0; node_n < cgraph->n_nodes && atomic_load_explicit(&tp->abort, memory_order_relaxed) != node_n; node_n++) {\n"
    "        struct ggml_tensor * node = cgraph->nodes[node_n];\n"
    "        if (rf_s >= 0) {\n"
    "            rf_k = (int) node->op * 64;\n"
    "            if ((node->op == GGML_OP_MUL_MAT || node->op == GGML_OP_MUL_MAT_ID) && node->src[0]) rf_k += (int) node->src[0]->type % 64;\n"
    "            rf_t0 = rf_now();\n"
    "        }\n")
sub(c, "            ggml_compute_forward(&params, node);\n        }\n",
    "            ggml_compute_forward(&params, node);\n        }\n"
    "        if (rf_s >= 0) { rf_t1 = rf_now(); }\n")
sub(c, "        if (node_n + 1 < cgraph->n_nodes) {\n            ggml_barrier(state->threadpool);\n        }\n    }\n",
    "        if (node_n + 1 < cgraph->n_nodes) {\n            ggml_barrier(state->threadpool);\n        }\n"
    "        if (rf_s >= 0) {\n"
    "            const double rf_t2 = rf_now();\n"
    "            rf_compute[rf_s][rf_k] += rf_t1 - rf_t0; rf_wall[rf_s][rf_k] += rf_t2 - rf_t0; rf_count[rf_s][rf_k]++; rf_nodes[rf_s]++;\n"
    "        }\n"
    "    }\n"
    "    if (rf_s >= 0) {\n"
    "        rf_graph_s[rf_s] += rf_now() - rf_g0;\n"
    "        if (++rf_graphs[rf_s] % 64 == 0) rf_dump();\n"
    "    }\n")

# 1c) ggml-cpu.c: optional two-level NUMA barrier (GGML_RF_BARRIER=1) in place of `omp barrier`:
#     threads first meet on a per-node counter, only the last thread of each node touches the global counter.
#     (Same idea as the barrier part of llama.cpp PR #14232.) Defined after ggml_numa_init's globals.
BAR = r'''
// ---- RAMForge two-level NUMA barrier (GGML_RF_BARRIER=1) ----
static int rf_barrier_on = -1;
static __thread int rf_tls_ith = 0;
static struct { atomic_int v; char pad[60]; } rf_node_cnt[GGML_NUMA_MAX_NODES];
static struct { atomic_int v; char pad[60]; } rf_glob_cnt;
static struct { atomic_int v; char pad[60]; } rf_gen;
static inline int rf_node_of(int ith, int nth, int nn) {
    return ramforge_numa_block > 0 ? (int) (((int64_t) ith * nn) / nth) : ith % nn;
}
static void rf_barrier(int n_threads) {
    const int nn = (int) g_state.numa.n_nodes;
    const int ith = rf_tls_ith;
    const int node = rf_node_of(ith, n_threads, nn);
    int members = 0, active = 0;
    for (int q = 0; q < nn; q++) {
        int m = 0;
        for (int i = 0; i < n_threads; i++) { if (rf_node_of(i, n_threads, nn) == q) m++; }
        if (q == node) members = m;
        if (m > 0) active++;
    }
    const int gen = atomic_load_explicit(&rf_gen.v, memory_order_acquire);
    if (atomic_fetch_add_explicit(&rf_node_cnt[node].v, 1, memory_order_acq_rel) == members - 1) {
        atomic_store_explicit(&rf_node_cnt[node].v, 0, memory_order_relaxed);
        if (atomic_fetch_add_explicit(&rf_glob_cnt.v, 1, memory_order_acq_rel) == active - 1) {
            atomic_store_explicit(&rf_glob_cnt.v, 0, memory_order_relaxed);
            atomic_fetch_add_explicit(&rf_gen.v, 1, memory_order_seq_cst);
            return;
        }
    }
    while (atomic_load_explicit(&rf_gen.v, memory_order_relaxed) == gen) {
        ggml_thread_cpu_relax();
    }
    atomic_thread_fence(memory_order_seq_cst);
}
'''
sub(c, "void ggml_barrier(struct ggml_threadpool * tp) {\n    int n_threads = atomic_load_explicit(&tp->n_graph, memory_order_relaxed) & GGML_THREADPOOL_N_THREADS_MASK;\n    if (n_threads == 1) {\n        return;\n    }\n",
    "void ggml_barrier(struct ggml_threadpool * tp) {\n    int n_threads = atomic_load_explicit(&tp->n_graph, memory_order_relaxed) & GGML_THREADPOOL_N_THREADS_MASK;\n    if (n_threads == 1) {\n        return;\n    }\n"
    "    if (rf_barrier_on < 0) { const char * e = getenv(\"GGML_RF_BARRIER\"); rf_barrier_on = (e && atoi(e) > 0) ? 1 : 0; }\n"
    "    if (rf_barrier_on && g_state.numa.n_nodes > 1) { rf_barrier(n_threads); return; }\n")
# the barrier needs g_state and ramforge_numa_block, which are defined later in the file: forward-declare
sub(c, "void ggml_barrier(struct ggml_threadpool * tp) {\n",
    "static void rf_barrier(int n_threads);\nstatic int rf_barrier_on;\n" "void ggml_barrier(struct ggml_threadpool * tp) {\n")
sub(c, "static int ramforge_numa_block = -1;", "static int ramforge_numa_block = -1;" + BAR.replace("static int rf_barrier_on = -1;", "static int rf_barrier_on = -1; // (tentative definition above)"))
sub(c, "    if (rf_prof_on < 0) { rf_prof_path", "    rf_tls_ith = state->ith;\n    if (rf_prof_on < 0) { rf_prof_path")

# 2) llama.cpp: NUMA-local weight placement after load
l = "src/llama.cpp"
sub(l, "#include <vector>\n",
    "#include <vector>\n#include <string>\n#include <chrono>\n#if defined(__linux__)\n#include <unistd.h>\n#include <sys/syscall.h>\n#endif\n")

HELPER = r'''
// ---- RAMForge ExpertFlow prototype: NUMA-local weight placement ----------------------------------
// With GGML_NUMA_BLOCK=1 and --numa distribute, compute thread ith runs on node ith*N/nth, and every
// matmul kernel used for decode on this CPU (repack Q4_K gemv/mul_mat_id, llamafile Q8_0, ggml mul_mat)
// splits src0 rows statically by ith when NUMA is on. This binds the rows each node's threads read to
// that node (per expert slice for 3-D expert tensors), so decode reads weights through the local memory
// channel instead of 3/4 remote (page interleave).
#if defined(__linux__)
static int rf_count_nodes() {
    int n = 0;
    for (;; n++) {
        std::string p = "/sys/devices/system/node/node" + std::to_string(n);
        if (access(p.c_str(), F_OK) != 0) break;
    }
    return n;
}

static int64_t rf_row_start(const ggml_tensor * t, bool repacked, int64_t ith, int64_t nth) {
    const int64_t nr = t->ne[1];
    if (ith >= nth) return nr;
    int64_t s;
    if (repacked && t->ne[2] > 1) {                 // repack forward_mul_mat_id: (ith*ne01)/nth, aligned up to 8
        s = (ith * nr) / nth; s = (s + 7) / 8 * 8;
    } else if (repacked) {                          // repack forward_mul_mat, NUMA: dr0 = ceil(nr/nth), aligned up to 8
        const int64_t dr = (nr + nth - 1) / nth; s = dr * ith; s = (s + 7) / 8 * 8;
    } else if (t->type == GGML_TYPE_Q8_0) {         // llamafile tinyBLAS_Q0_AVX gemm4xN: tiles of 4 rows, duty = ceil(tiles/nth)
        const int64_t tiles = nr / 4; const int64_t duty = (tiles + nth - 1) / nth; s = 4 * duty * ith;
    } else {                                        // ggml mul_mat NUMA path: dr0 = ceil(nr/nth)
        const int64_t dr = (nr + nth - 1) / nth; s = dr * ith;
    }
    return s < nr ? s : nr;
}

static void ramforge_place_weights(llama_model * model) {
    const char * e = getenv("LLAMA_RAMFORGE_PLACE");
    if (!e || atoi(e) <= 0) return;
    const int nn = rf_count_nodes();
    if (nn < 2) { fprintf(stderr, "ramforge: fewer than 2 NUMA nodes, placement skipped\n"); return; }
    const char * en = getenv("LLAMA_RAMFORGE_NTH");
    const int64_t nth = en ? atoll(en) : 24;
    const size_t pg = (size_t) sysconf(_SC_PAGESIZE);
    const int64_t min_bytes = 1 << 20;
    auto t0 = std::chrono::steady_clock::now();
    size_t placed = 0, failed = 0, n_calls = 0, n_t = 0, n_probe = 0, n_probe_ok = 0;
    std::vector<size_t> per_node(nn, 0);
    for (const auto & it : model->tensors_by_name) {
        const ggml_tensor * t = it.second;
        if (!t || !t->data || !t->buffer || !ggml_backend_buffer_is_host(t->buffer)) continue;
        if ((int64_t) ggml_nbytes(t) < min_bytes || t->ne[1] < 2 * nn) continue;
        if (it.first == "token_embd.weight") continue;   // get_rows: one row per token, any node is fine
        const bool repacked = strstr(ggml_backend_buffer_name(t->buffer), "REPACK") != nullptr;
        const int64_t nslices = t->ne[2] * t->ne[3];
        n_t++;
        for (int64_t sl = 0; sl < nslices; sl++) {
            const uintptr_t base = (uintptr_t) t->data + (uintptr_t) ((sl % t->ne[2]) * t->nb[2] + (sl / t->ne[2]) * t->nb[3]);
            for (int q = 0; q < nn; q++) {
                const int64_t r0 = rf_row_start(t, repacked, (q * nth) / nn, nth);
                const int64_t r1 = q == nn - 1 ? t->ne[1] : rf_row_start(t, repacked, ((q + 1) * nth) / nn, nth);
                if (r1 <= r0) continue;
                uintptr_t a = base + (uintptr_t) (r0 * t->nb[1]);
                uintptr_t b = base + (uintptr_t) (r1 * t->nb[1]);
                a = (a + pg / 2) / pg * pg;                // each page goes to the node that owns most of it
                b = (b + pg / 2) / pg * pg;
                if (b <= a) continue;
                unsigned long mask = 1ul << q;
                // mode MPOL_BIND = 2, flags MPOL_MF_MOVE = 2
                long rc = syscall(SYS_mbind, (void *) a, (unsigned long) (b - a), 2, &mask, (unsigned long) (nn + 1), 2);
                n_calls++;
                if (rc == 0) { placed += b - a; per_node[q] += b - a; } else { failed += b - a; }
                // verify: ask the kernel where the middle page of this range now lives (move_pages, query only)
                void * probe = (void *) (a + ((b - a) / pg / 2) * pg); int st = -1;
                if (syscall(SYS_move_pages, 0, 1ul, &probe, nullptr, &st, 0) == 0) { n_probe++; if (st == q) n_probe_ok++; }
            }
        }
    }
    const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
    std::string pn;
    for (int q = 0; q < nn; q++) { pn += (q ? " " : ""); pn += std::to_string(per_node[q] >> 20); }
    fprintf(stderr, "ramforge: placed %.2f GiB of %zu weight tensors on %d nodes (MiB per node: %s), %zu mbind calls, "
                    "%.2f GiB failed, probe %zu/%zu pages on the intended node, nth=%" PRId64 ", %.0f ms\n",
                    placed / 1073741824.0, n_t, nn, pn.c_str(), n_calls, failed / 1073741824.0, n_probe_ok, n_probe, nth, ms);
}
#else
static void ramforge_place_weights(llama_model *) {}
#endif
// ---------------------------------------------------------------------------------------------------

// Returns 0 on success, -1 on error, and -2 on cancellation via llama_progress_callback
'''
sub(l, "\n// Returns 0 on success, -1 on error, and -2 on cancellation via llama_progress_callback\n", HELPER)
sub(l, "        if (!model->load_tensors(ml)) {\n            return {-2, nullptr};\n        }\n",
    "        if (!model->load_tensors(ml)) {\n            return {-2, nullptr};\n        }\n\n        ramforge_place_weights(model);\n")
print("patched")
