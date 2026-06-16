# -*- coding: utf-8 -*-
"""
数据清洗脚本：读取原始 Excel 并同时生成系统一和系统二的配置模板（带列名智能匹配）
"""
import traceback
import pandas as pd
import re
import config


def generate_all_templates():
    print(f"📖 正在读取原始 Excel: '{config.RAW_EXCEL_FILE}', 工作表: '{config.RAW_SHEET_NAME}'...")
    
    try:
        # 1. 首次读取：完整载入指定 Sheet，不设表头（header=None）
        df_raw = pd.read_excel(config.RAW_EXCEL_FILE, sheet_name=config.RAW_SHEET_NAME, header=None)
        
        # 2. 寻找真实表头行
        header_row_idx = None
        for idx, row in df_raw.iterrows():
            row_vals = [str(x) for x in row.values]
            if any("数据名称" in x for x in row_vals):
                header_row_idx = idx
                break
        
        if header_row_idx is None:
            print("❌ 预处理失败：在 Excel 表格中未能匹配到包含 '数据名称' 的表头行，请确认 Sheet 名字是否正确。")
            print(f"当前 Sheet 下前几行的数据为：\n{df_raw.head(3)}")
            return False
            
        # 3. 切片操作：提取表头并去除空格
        headers = [str(col).strip() for col in df_raw.iloc[header_row_idx].values]
        df = df_raw.iloc[header_row_idx + 1:].copy()
        df.columns = headers
        
    except Exception as e:
        print("❌ 读取 Excel 原始结构或切片时发生崩溃：")
        traceback.print_exc()
        return False

    # ================== 核心升级：智能关键字模糊列名匹配 ==================
    col_unit_code = next((col for col in df.columns if "单位编码" in col), None)
    col_device_id = next((col for col in df.columns if "设备编码" in col), None)
    col_point_name = next((col for col in df.columns if "数据名称" in col), None)
    col_virtual_addr = next((col for col in df.columns if "虚拟地址" in col), None)

    print("📌 检测到列名映射关系如下:")
    print(f"   - [单位编码] 匹配列 -> {col_unit_code}")
    print(f"   - [设备编码] 匹配列 -> {col_device_id}")
    print(f"   - [数据名称] 匹配列 -> {col_point_name}")
    print(f"   - [虚拟地址] 匹配列 -> {col_virtual_addr}")

    # 检查必填核心列是否成功匹配
    missing_cols = []
    if not col_unit_code: missing_cols.append("单位编码")
    if not col_device_id: missing_cols.append("设备编码")
    if not col_point_name: missing_cols.append("数据名称")

    if missing_cols:
        print(f"\n❌ 预处理失败：未能从当前表格中找到必要的列: {', '.join(missing_cols)}")
        print(f"💡 当前表格检测到的所有列名为: {list(df.columns)}")
        print("请检查 `config.py` 中的 `RAW_SHEET_NAME` 对应的 Sheet 页内容是否为原始数据。")
        return False

    sys1_rows = []
    sys2_rows = []
    device_point_counters = {}

    try:
        for idx, row in df.iterrows():
            # 使用动态匹配到的列名读取数据
            unit_code = str(row[col_unit_code]).strip()
            device_id = str(row[col_device_id]).strip()
            point_name = str(row[col_point_name]).strip()
            raw_virtual_addr = row[col_virtual_addr] if col_virtual_addr else ""
            
            # 过滤掉空行
            if not point_name or point_name == 'nan' or device_id == 'nan':
                continue
                
            device_code = ""
            workshop_code = ""
            factory_code = ""

            # ------------------ 锻造厂 (TCHF) 编码拼接 ------------------
            if "TCHF" in unit_code.upper():
                factory_code = "0TCHF"
                nums = re.findall(r'\d+', device_id)
                furnace_num = "01"
                if nums:
                    furnace_num = f"{int(nums[-1]):02d}"
                    
                if "25MN" in device_id.upper():
                    workshop_code = "F01"
                    device_code = f"0TCHF010020225MN{furnace_num}"
                else:
                    workshop_code = "F02"
                    device_code = f"0TCHF0200502MT{furnace_num}"
            else:
                # 非锻造厂暂跳过
                continue

            # ------------------ 测点自增序号计算 ------------------
            if device_code not in device_point_counters:
                device_point_counters[device_code] = 1
            else:
                device_point_counters[device_code] += 1
                
            point_code = f"{device_code}_P{device_point_counters[device_code]:04d}"
            point_path = f"root.iec.{factory_code}.{workshop_code}.{device_code}"
            
            # 测点类型
            if "温度" in point_name:
                point_type = "温度"
            elif "电流" in point_name:
                point_type = "电流"
            else:
                point_type = "其他"

            # ------------------ 写入系统一结构 ------------------
            sys1_rows.append({
                "测点名称": point_name,
                "测点编码": point_code,
                "测点路径": point_path,
                "测点类型": point_type,
                "是否启用": "是"
            })

            # ------------------ 写入系统二结构 ------------------
            try:
                if pd.notna(raw_virtual_addr) and str(raw_virtual_addr).strip() != "":
                    addr_val = int(float(raw_virtual_addr))
                    formatted_addr = f"{addr_val:04d}"
                else:
                    formatted_addr = ""
            except Exception:
                formatted_addr = ""

            sys2_rows.append({
                "设备编码": device_code,
                "功能类型 (PROPERTY)": "PROPERTY",
                "类别 (过程数据、开关量、分析)": "过程数据",
                "功能名称": point_name,
                "原始点位": formatted_addr,
                "数据类型 (STRING、LONG、BOOLEAN、DOUBLE、ENUM)": "DOUBLE"
            })

        # ------------------ 保存输出模板 ------------------
        if sys1_rows:
            pd.DataFrame(sys1_rows).to_excel(config.SYSTEM1_TEMPLATE_FILE, index=False)
            print(f"✅ 系统一配置模板已生成: '{config.SYSTEM1_TEMPLATE_FILE}'")

        if sys2_rows:
            pd.DataFrame(sys2_rows).to_excel(config.SYSTEM2_TEMPLATE_FILE, index=False)
            print(f"✅ 系统二配置模板已生成: '{config.SYSTEM2_TEMPLATE_FILE}'")
            return True
        else:
            print("\n⚠️ 匹配结束，但未能提取到任何符合条件的配置行（如单位编码为 'TCHF' 的行）。请确认原始表格的数据内容。")
            return False

    except Exception as e:
        print("❌ 解析数据行或输出 Excel 时发生崩溃：")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    generate_all_templates()