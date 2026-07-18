from __future__ import annotations
import argparse,json
from packages.governance_engine import PolicyEngine
from packages.memory_engine import MemoryStore
def main()->None:
    parser=argparse.ArgumentParser(prog="ai-control-plane");sub=parser.add_subparsers(dest="command",required=True)
    start=sub.add_parser("memory-start");start.add_argument("summary")
    policy=sub.add_parser("policy-check");policy.add_argument("action");policy.add_argument("--environment",default="local");policy.add_argument("--command",default="")
    args=parser.parse_args()
    if args.command=="memory-start":print(MemoryStore().start_session(args.summary))
    else:print(json.dumps(PolicyEngine().decide(args.environment,args.action,args.command).__dict__,indent=2))
if __name__=="__main__":main()
