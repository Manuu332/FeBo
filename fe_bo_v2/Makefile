.PHONY: run test install clean observe logs

run:
	python main.py

test:
	python -m pytest tests/test_merged.py -v --tb=short

test-quick:
	python -m pytest tests/test_merged.py -q --tb=line

install:
	bash install.sh

observe:
	@echo "=== Emotion Drift (last 20 turns) ==="; \
	[ -f logs/emotion_drift.jsonl ] && \
	python3 -c "import sys,json; [print(f'turn={d[\"turn\"]:4d} mood={d[\"mood\"]:<12} val={d[\"v\"]:+.2f} cur={d[\"c\"]:.2f}') for d in [json.loads(l) for l in open('logs/emotion_drift.jsonl')][-20:]]" \
	|| echo "(no data yet)"; \
	echo ""; echo "=== Health Events ==="; \
	[ -f logs/health.jsonl ] && \
	python3 -c "import sys,json; [print(d.get('warning','?')) for d in [json.loads(l) for l in open('logs/health.jsonl')][-5:]]" \
	|| echo "(no events)"

logs:
	tail -f logs/febo.log

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -name "*.pyc" -delete 2>/dev/null; true

clean-data:
	@read -p "Delete all FeBo memories? [y/N] " ans && [ "$$ans" = "y" ] && \
	rm -rf memory/*.json memory/*.db logs/*.jsonl logs/*.log data/ || echo "Aborted."
