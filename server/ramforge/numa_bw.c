// RAMForge numa_bw: STREAM-style read bandwidth per NUMA node, local vs remote vs interleaved.
// Build: gcc -O3 -march=native -pthread numa_bw.c -o numa_bw
// Usage: numa_bw <mode> [seconds]
//   modes: node:<cpu_node>:<mem_node>     6 threads on cpu_node read memory bound to mem_node
//          local-all                      every node's threads read their own node's memory (NUMA-local ceiling)
//          interleave-all                 all threads read one page-interleaved buffer (what llama.cpp sees today)
//          onenode-all:<mem_node>         all threads read memory on a single node
// Threads: one per physical core (the first n_cores/n_nodes CPUs of each node's cpulist).
#define _GNU_SOURCE
#include <immintrin.h>
#include <pthread.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

#define MPOL_BIND 2
#define MPOL_INTERLEAVE 3
#define MPOL_MF_MOVE (1 << 1)
#define MAXN 8

static int n_nodes = 0, node_cpus[MAXN][64], node_ncpu[MAXN];
static double secs = 3.0;

static void read_topology(void) {
    for (int n = 0; n < MAXN; n++) {
        char p[128]; snprintf(p, sizeof p, "/sys/devices/system/node/node%d/cpulist", n);
        FILE * f = fopen(p, "r"); if (!f) break;
        char buf[512]; if (!fgets(buf, sizeof buf, f)) { fclose(f); break; } fclose(f);
        node_ncpu[n] = 0;
        for (char * s = strtok(buf, ",\n"); s; s = strtok(NULL, ",\n")) {
            int a, b; if (sscanf(s, "%d-%d", &a, &b) == 2) { for (int c = a; c <= b; c++) node_cpus[n][node_ncpu[n]++] = c; }
            else if (sscanf(s, "%d", &a) == 1) node_cpus[n][node_ncpu[n]++] = a;
        }
        n_nodes = n + 1;
    }
}

static void * alloc_policy(size_t bytes, int mode, unsigned long mask) {
    void * p = mmap(NULL, bytes, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (p == MAP_FAILED) { perror("mmap"); exit(1); }
    if (syscall(SYS_mbind, p, bytes, mode, &mask, MAXN + 1, MPOL_MF_MOVE) != 0) { perror("mbind"); exit(1); }
    memset(p, 1, bytes);  // fault pages in under the policy
    return p;
}

typedef struct { int cpu_node, core_idx; const char * buf; size_t bytes; double gbps; pthread_barrier_t * bar; } job_t;

static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }

static void * worker(void * arg) {
    job_t * j = arg;
    cpu_set_t cs; CPU_ZERO(&cs);
    // physical cores first: the first half of the node's cpulist are distinct cores on this box
    CPU_SET(node_cpus[j->cpu_node][j->core_idx], &cs);
    pthread_setaffinity_np(pthread_self(), sizeof cs, &cs);
    pthread_barrier_wait(j->bar);
    __m256i acc = _mm256_setzero_si256();
    size_t done = 0; double t0 = now(), t1;
    do {
        const __m256i * p = (const __m256i *) j->buf;
        size_t n = j->bytes / 32;
        for (size_t i = 0; i < n; i += 4) {
            acc = _mm256_xor_si256(acc, _mm256_load_si256(p + i));
            acc = _mm256_xor_si256(acc, _mm256_load_si256(p + i + 1));
            acc = _mm256_xor_si256(acc, _mm256_load_si256(p + i + 2));
            acc = _mm256_xor_si256(acc, _mm256_load_si256(p + i + 3));
        }
        done += j->bytes; t1 = now();
    } while (t1 - t0 < secs);
    volatile int sink = _mm256_extract_epi32(acc, 0); (void) sink;
    j->gbps = done / (t1 - t0) / 1e9;
    return NULL;
}

static double run(job_t * jobs, int n) {
    pthread_barrier_t bar; pthread_barrier_init(&bar, NULL, n);
    pthread_t th[256];
    for (int i = 0; i < n; i++) { jobs[i].bar = &bar; pthread_create(&th[i], NULL, worker, &jobs[i]); }
    double tot = 0; for (int i = 0; i < n; i++) { pthread_join(th[i], NULL); tot += jobs[i].gbps; }
    return tot;
}

int main(int argc, char ** argv) {
    if (argc < 2) { fprintf(stderr, "usage: numa_bw node:C:M|local-all|interleave-all|onenode-all:M [seconds]\n"); return 2; }
    if (argc > 2) secs = atof(argv[2]);
    read_topology();
    int cores = node_ncpu[0] / 2;  // SMT: second half are siblings
    const size_t per_thread = 256ul << 20;  // 256 MiB per thread >> L3
    job_t jobs[256]; int n = 0;
    const char * m = argv[1];
    if (!strncmp(m, "node:", 5)) {
        int c, mem; sscanf(m + 5, "%d:%d", &c, &mem);
        char * buf = alloc_policy(per_thread * cores, MPOL_BIND, 1ul << mem);
        for (int i = 0; i < cores; i++) jobs[n++] = (job_t){c, i, buf + i * per_thread, per_thread, 0, 0};
    } else if (!strcmp(m, "local-all")) {
        for (int nd = 0; nd < n_nodes; nd++) {
            char * buf = alloc_policy(per_thread * cores, MPOL_BIND, 1ul << nd);
            for (int i = 0; i < cores; i++) jobs[n++] = (job_t){nd, i, buf + i * per_thread, per_thread, 0, 0};
        }
    } else if (!strcmp(m, "interleave-all") || !strncmp(m, "onenode-all:", 12)) {
        unsigned long mask = (1ul << n_nodes) - 1; int mode = MPOL_INTERLEAVE;
        if (m[0] == 'o') { mask = 1ul << atoi(m + 12); mode = MPOL_BIND; }
        size_t pt = per_thread / 2;
        char * buf = alloc_policy(pt * cores * n_nodes, mode, mask);
        for (int nd = 0; nd < n_nodes; nd++)
            for (int i = 0; i < cores; i++) { jobs[n] = (job_t){nd, i, buf + n * pt, pt, 0, 0}; n++; }
    } else { fprintf(stderr, "bad mode\n"); return 2; }
    double tot = run(jobs, n);
    printf("{\"mode\":\"%s\",\"threads\":%d,\"seconds\":%.1f,\"read_gbps\":%.2f", m, n, secs, tot);
    if (!strcmp(m, "local-all")) {
        printf(",\"per_node\":[");
        for (int nd = 0; nd < n_nodes; nd++) { double s = 0; for (int i = 0; i < cores; i++) s += jobs[nd * cores + i].gbps; printf("%s%.2f", nd ? "," : "", s); }
        printf("]");
    }
    printf("}\n");
    return 0;
}
