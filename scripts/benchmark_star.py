"""Opt-in real local model speed test. Example:

python -m scripts.benchmark_star --model 'your-installed-model' --parallel 2
"""
import argparse
import asyncio
import json

from star.inference_benchmark import benchmark_local_model


def main():
    parser=argparse.ArgumentParser(description="Measure actual STAR localhost chat throughput")
    parser.add_argument("--endpoint",default="http://127.0.0.1:8080/v1",
                        help="Local loopback OpenAI-compatible endpoint only")
    parser.add_argument("--model",required=True,help="Model ID currently reported by the local engine")
    parser.add_argument("--parallel",type=int,choices=[1,2,3,4],default=1,
                        help="Concurrent request limit; start at 1 on smaller GPUs")
    parser.add_argument("--requests",type=int,choices=list(range(1,13)),default=4)
    args=parser.parse_args()
    result=asyncio.run(benchmark_local_model(
        args.endpoint,args.model,parallel=args.parallel,requests=args.requests))
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()
