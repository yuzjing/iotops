# -*- coding: utf-8 -*-
"""
系统三（Modbus TCP 设备管理系统）自动添加设备脚本
"""
import asyncio
import traceback
import re  # 已修正：移至顶部全局导入
import pandas as pd
from playwright.async_api import async_playwright

import config


def get_unique_devices():
    """
    读取原始 Excel，提取出唯一的设备列表及对应的 IP、端口信息
    """
    print(f"📖 正在从 '{config.RAW_EXCEL_FILE}' 中提取唯一设备列表...")
    try:
        # 1. 首次读取：完整载入指定 Sheet，不设表头
        df_raw = pd.read_excel(config.RAW_EXCEL_FILE, sheet_name=config.RAW_SHEET_NAME, header=None)
        
        # 寻找包含“数据名称”的真实表头行
        header_row_idx = None
        for idx, row in df_raw.iterrows():
            row_vals = [str(x) for x in row.values]
            if any("数据名称" in x for x in row_vals):
                header_row_idx = idx
                break
                
        if header_row_idx is None:
            print("❌ 错误：未能在 Excel 中定位到有效表头，请确认 Sheet 名字。")
            return []
            
        headers = [str(col).strip() for col in df_raw.iloc[header_row_idx].values]
        df = df_raw.iloc[header_row_idx + 1:].copy()
        df.columns = headers
        
        # 智能匹配需要的关键数据列
        col_device_id = next((col for col in df.columns if "设备编码" in col), None)
        col_ip = next((col for col in df.columns if "IP" in col or "IP地址" in col), None)
        col_port_station = next((col for col in df.columns if "插槽" in col or "端口" in col or "站号" in col), None)
        
        if not col_device_id or not col_ip:
            print("❌ 错误：原始表格中缺少必要列（设备编码 或 IP地址）。")
            return []
            
        # 去重，只保留唯一的设备（例如多行 25MN-20 只保留第一行）
        df_unique = df.drop_duplicates(subset=[col_device_id]).copy()
        
        devices = []
        for idx, row in df_unique.iterrows():
            device_name = str(row[col_device_id]).strip()
            device_ip = str(row[col_ip]).strip()
            
            # 读取原始点位/端口配置
            raw_port = str(row[col_port_station]).strip() if col_port_station else ""
            device_port = 502  # 默认 Modbus TCP 端口
            device_station = 1  # 默认从站 ID
            
            # 简单尝试从插槽/端口列解析出数据（如果包含 503 等端口号）
            if raw_port and raw_port != 'nan':
                nums = re.findall(r'\d+', raw_port)
                if nums:
                    # 如果写的是 503 等，我们暂定为端口
                    device_port = int(nums[0])
            
            if device_name and device_name != 'nan':
                devices.append({
                    "name": device_name,
                    "ip": device_ip,
                    "port": device_port,
                    "station_id": device_station
                })
                
        print(f"✅ 成功提取到 {len(devices)} 个唯一的设备。")
        return devices
        
    except Exception as e:
        print("❌ 解析 Excel 提取设备列表时发生崩溃：")
        traceback.print_exc()
        return []


async def main():
    # 提取唯一的设备配置列表
    devices = get_unique_devices()
    if not devices:
        print("❌ 未获取到有效设备数据，程序退出。")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            # 1. 登录系统三
            print("🔐 正在登录系统三...")
            await page.goto(config.SYSTEM3_LOGIN_URL)
            await page.get_by_placeholder("用户名").fill(config.SYSTEM3_USERNAME)
            await page.get_by_placeholder("密码").fill(config.SYSTEM3_PASSWORD)
            
            # 点击登录按钮
            await page.locator('button:has-text("登录")').click()
            await page.wait_for_timeout(1500)
            
            # 2. 点击左侧“设备管理”导航菜单
            print("📂 导航至左侧 [设备管理] 页面...")
            # 匹配左侧含有“设备管理”字样的侧边栏元素
            await page.locator('xpath=//div[contains(@class, "sidebar")]//*[text()="设备管理"] | //*[text()="设备管理"]').first.click()
            
            # 等待右侧列表加载出“添加设备”按钮，保证页面完全载入
            await page.wait_for_selector('text="添加设备"', state="visible", timeout=15000)
            await page.wait_for_timeout(1000)

            # 3. 循环添加设备
            for dev in devices:
                print(f"\n🚀 正在添加设备: [{dev['name']}] (IP: {dev['ip']})")
                
                # 3.1 点击右上角的“添加设备”
                await page.locator('text="添加设备"').first.click()
                await page.wait_for_timeout(1000)  # 等待表单弹窗展开
                
                # ====================================================================
                # 📝 [添加设备表单填写区]
                # 由于此处没有弹窗截图，以下为您编写了通用定位。若运行报错，请根据实际弹窗微调：
                # ====================================================================
                
                # 1. 设备名称 (placeholder 通常为 "请输入设备名称" 或 "设备名称")
                name_input = page.get_by_placeholder("请输入设备名称")
                if await name_input.count() == 0:
                    name_input = page.get_by_placeholder("设备名称")
                await name_input.fill(dev['name'])
                
                # 2. IP 地址
                ip_input = page.get_by_placeholder("请输入IP")
                if await ip_input.count() == 0:
                    ip_input = page.get_by_placeholder("IP地址")
                await ip_input.fill(dev['ip'])
                
                # 3. 端口 (Modbus TCP 默认 502)
                port_input = page.get_by_placeholder("请输入端口")
                if await port_input.count() == 0:
                    port_input = page.get_by_placeholder("端口")
                if await port_input.count() > 0:
                    await port_input.fill(str(dev['port']))
                
                # 4. 从站 ID / 站号 (通常默认 1)
                station_input = page.get_by_placeholder("请输入从站ID")
                if await station_input.count() == 0:
                    station_input = page.get_by_placeholder("从站ID")
                if await station_input.count() > 0:
                    await station_input.fill(str(dev['station_id']))

                # 5. 点击保存/确定提交
                # 寻找表单弹窗中的“确定”或“保存”按钮并点击
                submit_btn = page.locator('xpath=//button//*[contains(text(), "确定")] | //button//*[contains(text(), "保存")] | //button[contains(text(), "确定")]').last
                await submit_btn.click()
                
                # 等待提交完毕，弹窗关闭
                await page.wait_for_timeout(1500)
                print(f"   ✅ 设备 [{dev['name']}] 已成功添加。")

            print("\n🎉 系统三所有设备添加工作执行完毕...")
            input("请按回车键关闭浏览器...")
            
        except Exception as e:
            print(f"\n💥 系统三运行异常: {e}")
            input("程序暂停，请检查并按回车键退出...")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())