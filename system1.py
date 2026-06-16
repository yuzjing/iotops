# -*- coding: utf-8 -*-
"""
系统一自动化导入脚本
"""
import asyncio
import os
import pandas as pd
from playwright.async_api import async_playwright

import config
from template_generator import generate_all_templates


def get_tree_codes(device_code):
    """
    根据标准设备编码解析出父级路径列表
    """
    device_code = device_code.upper().replace('O', '0')
    codes = []
    if device_code.startswith("0TCHF"):
        codes.append("0TCHF")
        if len(device_code) >= 7:
            codes.append(device_code[:7])
        if len(device_code) >= 12:
            codes.append(device_code[:12])
        codes.append(device_code)
    elif device_code.startswith("0TCAA"):
        codes.append("0TCAA")
        if len(device_code) > 5:
            codes.append(device_code)
    elif device_code.startswith("0TCBC"):
        codes.append("0TCBC")
        if len(device_code) > 5:
            codes.append(device_code)
    else:
        codes.append(device_code)
    return codes


async def expand_and_find_device(page, device_code):
    right_pane = page.locator(".splitter-paneR")
    codes = get_tree_codes(device_code)
    print(f"🌲 定位设备树路径: {' -> '.join(codes)}")
    
    for i, code in enumerate(codes):
        text_selector = f'xpath=//*[contains(text(), "({code})")]'
        text_locator = right_pane.locator(text_selector).first
        await text_locator.wait_for(state="visible", timeout=10000)
        
        if i == len(codes) - 1:
            break
            
        arrow_selector = (
            f'xpath=//*[contains(text(), "({code})")]'
            f'/ancestor::*[contains(@class, "node") or contains(@class, "content")][1]'
            f'//*[contains(@class, "expand") or contains(@class, "caret") or '
            f'contains(@class, "switcher") or contains(@class, "arrow")]'
        )
        arrow_locator = right_pane.locator(arrow_selector).first
        if await arrow_locator.count() > 0:
            arrow_class = await arrow_locator.get_attribute("class") or ""
            if "expanded" not in arrow_class.lower() and "is-reverse" not in arrow_class.lower():
                await arrow_locator.click()
                await page.wait_for_timeout(800)
        else:
            await text_locator.dblclick()
            await page.wait_for_timeout(800)


async def add_measurement_point(page, device_code, point_name, point_code, point_path, point_type):
    right_pane = page.locator(".splitter-paneR")
    device_code_normalized = device_code.upper().replace('O', '0')
    device_selector = f'xpath=//*[contains(text(), "({device_code_normalized})")]'
    
    device_node = right_pane.locator(device_selector).first
    await device_node.scroll_into_view_if_needed()
    await device_node.click(button="right")
    await page.wait_for_timeout(500)
    
    add_btn = right_pane.locator("#context-menu").locator('text="添加"')
    await add_btn.click()
    await page.wait_for_timeout(1000)
    
    # 选择节点类型
    node_type_select = page.get_by_placeholder("请选择节点类型")
    await node_type_select.click()
    await page.wait_for_timeout(500)
    
    node_type_option = page.locator(
        'xpath=//div[contains(@class, "el-select-dropdown") and not(contains(@style, "display: none"))]'
        '//li[contains(@class, "el-select-dropdown__item")][contains(., "监测量")]'
    ).first
    await node_type_option.click()
    await page.wait_for_timeout(1000)
    
    # 填充基础字段
    await page.get_by_placeholder("请输入测点名称").fill(point_name)
    await page.get_by_placeholder("请输入测点编码").fill(point_code)
    
    # 路径与类型滚动定位并填写
    path_input = page.get_by_placeholder("请输入测点路径")
    await path_input.scroll_into_view_if_needed()
    await page.wait_for_timeout(300)
    await path_input.fill(point_path)
    
    type_select = page.locator('xpath=//input[contains(@placeholder, "数据类型")]').first
    await type_select.scroll_into_view_if_needed()
    await type_select.click()
    await page.wait_for_timeout(500)
    
    option_xpath = (
        f'xpath=//div[contains(@class, "el-select-dropdown") and not(contains(@style, "display: none"))]'
        f'//li[contains(@class, "el-select-dropdown__item")]//*[text()="{point_type}"] | '
        f'//div[contains(@class, "el-select-dropdown") and not(contains(@style, "display: none"))]'
        f'//li[contains(@class, "el-select-dropdown__item")][contains(., "{point_type}")]'
    )
    type_option = page.locator(option_xpath).first
    if await type_option.count() > 0:
        await type_option.click()
        await page.wait_for_timeout(500)
    else:
        print(f"   ⚠️ 下拉框未匹配到类型 '{point_type}'，跳过类型设定")
        await page.mouse.click(10, 10)
        await page.wait_for_timeout(300)
        
    submit_btn = page.locator('xpath=//button//*[contains(text(), "确定")] | //button[contains(text(), "确定")]').last
    await submit_btn.scroll_into_view_if_needed()
    await submit_btn.click()
    await page.wait_for_timeout(1500)
    print(f"   ✅ 已添加测点: {point_name} ({point_code})")


async def main():
    # 检查标准模板文件是否存在，如果不存在则自动预处理原始 Excel (新变量：config.SYSTEM1_TEMPLATE_FILE)
    if not os.path.exists(config.SYSTEM1_TEMPLATE_FILE):
        print(f"🔍 未检测到系统一标准中间文件 '{config.SYSTEM1_TEMPLATE_FILE}'，正在执行自动预处理转换...")
        success = generate_all_templates()
        if not success:
            print("❌ 预处理失败，程序退出。")
            return
            
    try:
        # 新变量：config.SYSTEM1_TEMPLATE_FILE 与 config.SYSTEM1_SHEET_NAME
        df = pd.read_excel(config.SYSTEM1_TEMPLATE_FILE, sheet_name=config.SYSTEM1_SHEET_NAME)
        df.columns = df.columns.str.strip()
        df = df[df['是否启用'].astype(str).str.strip() == '是']
        
        def extract_device_code(val):
            return str(val).split('_')[0].upper().replace('O', '0').strip()
            
        df['device_code'] = df['测点编码'].apply(extract_device_code)
        grouped_data = df.groupby('device_code')
        print(f"📊 成功加载标准配置。共需配置 {len(grouped_data)} 台设备。")
    except Exception as e:
        print(f"❌ 加载配置文件发生错误: {e}")
        return

    # 启动浏览器端自动化
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            print("🔐 正在登录系统一...")
            # 新变量：config.SYSTEM1_LOGIN_URL, config.SYSTEM1_USERNAME, config.SYSTEM1_PASSWORD
            await page.goto(config.SYSTEM1_LOGIN_URL)
            await page.fill('input[placeholder="Username"]', config.SYSTEM1_USERNAME)
            await page.fill('input[placeholder="Password"]', config.SYSTEM1_PASSWORD)
            await page.click('button:has-text("Login")')
            await page.wait_for_url("**/dms/index")
            
            print("📂 导航至设备树层级管理...")
            # 新变量：config.SYSTEM1_MENU_L1 与 config.SYSTEM1_MENU_L2
            await page.click(f'text={config.SYSTEM1_MENU_L1}')
            await page.wait_for_selector(f'text={config.SYSTEM1_MENU_L2}', state="visible")
            await page.click(f'text={config.SYSTEM1_MENU_L2}')
            await page.wait_for_timeout(2000)
            
            for device_code, group in grouped_data:
                if not device_code:
                    continue
                print(f"\n🚀 开始导入设备组: [{device_code}]，内含 {len(group)} 个测点")
                try:
                    await expand_and_find_device(page, device_code)
                    for idx, row in group.iterrows():
                        await add_measurement_point(
                            page, 
                            device_code, 
                            str(row['测点名称']).strip(), 
                            str(row['测点编码']).strip(), 
                            str(row['测点路径']).strip(), 
                            str(row['测点类型']).strip()
                        )
                except Exception as ex:
                    print(f"❌ 处理设备 [{device_code}] 发生故障: {ex}")
                    continue
                    
            print("\n🎉 任务全部导入结束，请人工复核...")
            input("回车键关闭浏览器并安全退出...")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())