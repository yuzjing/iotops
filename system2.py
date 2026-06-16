# -*- coding: utf-8 -*-
"""
系统二自动化配置与导入脚本 (精准树展开 + 预留处理逻辑)
"""
import asyncio
import os
import pandas as pd
from playwright.async_api import async_playwright

import config
from template_generator import generate_all_templates


def get_tree_codes(device_code):
    """
    根据设备编码解析出父级路径列表
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
    return codes


async def expand_and_select_device_sys2(page, device_code):
    """
    在系统二的 [设备分类] 树结构中，精准点击前面的 + 号展开，并最终单选中目标设备
    """
    codes = get_tree_codes(device_code)
    print(f"🌲 正在系统二树结构中定位设备: {' -> '.join(codes)}")
    
    for i, code in enumerate(codes):
        # 1. 寻找包含当前层级编码文本的单行内容容器
        # 严格排除 'node' 类名，防止子层级行定位时误匹配到父层级的 el-tree-node 容器中
        row_container = page.locator(".el-tree-node__content").filter(has=page.locator(f'text=[{code}]')).first
        
        if await row_container.count() == 0:
            row_container = page.locator("[class*='content'], [class*='item']").filter(has=page.locator(f'text=[{code}]')).first
            
        # 等待行容器完全加载并可见
        await row_container.wait_for(state="visible", timeout=10000)
        
        # 2. 如果是最后一级叶子节点，点击文本选中并结束
        if i == len(codes) - 1:
            print(f"   🎯 点击选中最终设备文本: [{code}]")
            text_node = row_container.locator(f'text=[{code}]').first
            await text_node.click(force=True)
            await page.wait_for_timeout(1500)  # 等待右侧面板数据渲染
            break
            
        # 3. 如果是中间节点，检查下一级节点是否在页面上可见
        next_code = codes[i + 1]
        next_locator = page.locator(f'text=[{next_code}]').first
        
        # 只要下一级节点在页面上不可见，说明当前节点折叠，必须执行展开操作
        if not await next_locator.is_visible():
            # 优先寻找行内容器中的自定义 [+] 状态图片 (即 img 元素)
            # 这是一个极度精准的定位方案：因为自定义 [+] 的小方块实际上就是绝对定位在最上方的 img 元素
            img_locator = row_container.locator("img").first
            
            if await img_locator.count() > 0:
                print(f"   ➕ [图片定位] 点击展开节点前置的 [+] 图标: [{code}]")
                # 穿透点击图片，Playwright 会自动透过 pointer-events: none 作用在下方的真实展开区域
                await img_locator.click(force=True)
                await page.wait_for_timeout(1200)  # 等待展开动画过渡
                
            else:
                # 备用：如果未找到自定义图片，尝试定位标准展开图标并强制点击
                arrow_locator = row_container.locator(".el-tree-node__expand-icon").first
                if await arrow_locator.count() > 0:
                    print(f"   ➕ [标准定位] 点击展开节点前置的 [+] 按钮: [{code}]")
                    await arrow_locator.click(force=True)
                    await page.wait_for_timeout(1200)

async def main():
    # 确保生成最新的配置数据
    if not os.path.exists(config.SYSTEM2_TEMPLATE_FILE):
        print(f"🔍 未检测到系统二标准配置，正在自动生成...")
        success = generate_all_templates()
        if not success:
            print("❌ 数据转换预处理失败，程序退出。")
            return

    try:
        df = pd.read_excel(config.SYSTEM2_TEMPLATE_FILE, sheet_name=config.SYSTEM2_SHEET_NAME)
        unique_devices = df['设备编码'].unique()
        print(f"📊 成功加载配置。共定位到 {len(unique_devices)} 台目标设备。")
    except Exception as e:
        print(f"❌ 读取配置数据失败: {e}")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            # 1. 登录系统二
            print("🔐 正在登录系统二...")
            await page.goto(config.SYSTEM2_LOGIN_URL)
            await page.get_by_placeholder("Username").fill(config.SYSTEM2_USERNAME)
            await page.get_by_placeholder("Password").fill(config.SYSTEM2_PASSWORD)
            
            # 点击登录
            await page.locator('button:has-text("Login")').click()
            await page.wait_for_timeout(1500)
            
            # 2. 导航至顶部 [设备管理] 页面
            print("📂 导航至顶部 [设备管理] 页面...")
            await page.locator('text="设备管理"').first.click()
            # 确保左侧树状区域的“设备分类”加载完毕后再进行树节点点击
            await page.wait_for_selector('text="设备分类"', state="visible", timeout=15000)
            await page.wait_for_timeout(1500)

            # 3. 开始遍历目标设备并执行配置
            for device_code in unique_devices:
                if not device_code:
                    continue
                
                print(f"\n🚀 开始处理设备: [{device_code}]")
                # 3.1 逐步展开并最终点击选中该炉子
                await expand_and_select_device_sys2(page, device_code)
                
                # ====================================================================
                # 📝 [在此处编写您自定义的后续录入或配置处理逻辑]
                # 目前已为您精准定位并点击选中了该炉子，右侧面板已经加载对应设备内容。
                # ====================================================================
                print(f"   💡 设备 [{device_code}] 已成功选中，已停留在该页面。")
                
                # 示例占位延迟，以便调试观察
                await page.wait_for_timeout(1000)
                
            print("\n🎉 系统二树结构定位工作执行完毕...")
            input("请按回车键关闭浏览器...")
            
        except Exception as e:
            print(f"\n💥 系统二运行异常: {e}")
            input("程序暂停，请检查并按回车键退出...")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())