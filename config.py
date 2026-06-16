# -*- coding: utf-8 -*-
"""
统一配置文件 config.py
"""
# 正确的做法
from dotenv import load_dotenv  # 需要先安装：pip install python-dotenv
import os

# 这行代码才是关键：将 .env 文件中的变量加载到环境变量中
load_dotenv()



# ==================== 一、通用 Excel 文件配置 ====================
RAW_EXCEL_FILE = os.getenv('RAW_EXCEL_FILE')
RAW_SHEET_NAME = os.getenv('RAW_SHEET_NAME')

# ==================== 二、系统一配置 ====================
SYSTEM1_LOGIN_URL = os.getenv('SYSTEM1_LOGIN_URL')
SYSTEM1_USERNAME = os.getenv('SYSTEM1_USERNAME')
SYSTEM1_PASSWORD = os.getenv('SYSTEM1_PASSWORD')
SYSTEM1_TEMPLATE_FILE = os.getenv('SYSTEM1_TEMPLATE_FILE')
SYSTEM1_SHEET_NAME = os.getenv('SYSTEM1_SHEET_NAME')
SYSTEM1_MENU_L1 = os.getenv('SYSTEM1_MENU_L1')
SYSTEM1_MENU_L2 = os.getenv('SYSTEM1_MENU_L2')

# ==================== 三、系统二配置 ====================
SYSTEM2_LOGIN_URL = os.getenv('SYSTEM2_LOGIN_URL')
SYSTEM2_USERNAME = os.getenv('SYSTEM2_USERNAME')
SYSTEM2_PASSWORD = os.getenv('SYSTEM2_PASSWORD')
SYSTEM2_TEMPLATE_FILE = os.getenv('SYSTEM2_TEMPLATE_FILE')
SYSTEM2_SHEET_NAME = os.getenv('SYSTEM2_SHEET_NAME')

# ==================== 三、系统二配置 ====================
SYSTEM3_LOGIN_URL = os.getenv('SYSTEM3_LOGIN_URL')
SYSTEM3_USERNAME = os.getenv('SYSTEM3_USERNAME')
SYSTEM3_PASSWORD = os.getenv('SYSTEM3_PASSWORD')
SYSTEM3_TEMPLATE_FILE = os.getenv('SYSTEM3_TEMPLATE_FILE')
SYSTEM3_SHEET_NAME = os.getenv('SYSTEM3_SHEET_NAME')