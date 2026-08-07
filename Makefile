.PHONY: install demo test dashboard clean

install:
	python -m pip install -e ".[dev,ai]"

demo:
	auction-sim --auctions 10000 --seed 42

test:
	pytest

dashboard:
	streamlit run dashboard/app.py

clean:
	rm -f data/raw/*.parquet data/staging/*.parquet data/warehouse/*.duckdb data/warehouse/*.wal
	rm -f artifacts/*.csv artifacts/*.json artifacts/*.md
