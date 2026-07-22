# software

Research pipeline for semantic-gateway. See `../research/plan.md` for the
experiment contract and `IMPLEMENTATION_NOTES.md` for design decisions.

## Layout

```
semantic_gateway/   shared package: manifest, wire format, policies,
                    proxy (AP), sender, receiver, decodability, summarize
model/              king-side: manifest builder, fine-tune, trace evaluation,
                    split-point feature extraction (RQ3)
testbed/netns.sh    snd -> ap -> rcv network namespaces + tc netem delay
experiments/        runnable experiment scripts (smoke.sh first)
tests/              pytest unit tests (decodability, policies, wire format)
```

## Quick start (pipeline, any Linux)

```bash
pip install -e .[test] && pytest
sudo ./testbed/netns.sh up
sudo SMOKE_OUT=/tmp/sgw-smoke ./experiments/smoke.sh
```

## Quick start (model side, king)

```powershell
# manifests from real UCF101 encodes
python model\prepare_manifests.py --ucf-dir ...\UCF-101 --split-file ...\testlist01.txt --out manifests_test01.jsonl
# one frozen checkpoint for all experiments
python model\finetune.py --ucf-dir ...\UCF-101 --splits-dir ...\ucfTrainTestlist --out-dir ckpt
# accuracy of one network run
python model\evaluate_trace.py --trace RUN\trace.jsonl --manifests manifests_test01.jsonl --ckpt ckpt\r2plus1d18_ucf101_seed0.pt --ucf-dir ... --splits-dir ... --out RUN\accuracy.json
```
