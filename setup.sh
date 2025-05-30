#!/bin/bash

source .venv/bin/activate
python resources/get_wdi_data.py --featured
python resources/paraphrase_indicators.py
python franklin/fill_templates.py -n 100
