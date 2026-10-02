# -*- coding: utf-8 -*-
"""Compatibility entry point for StockLens Pro.

启动：
    streamlit run stock_strategy_dashboard_pro_pie_v5.py --server.port 8501 --server.address 0.0.0.0
"""

from stocklens.app import main


if __name__ == "__main__":
    main()
