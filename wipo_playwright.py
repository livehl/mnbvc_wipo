import _thread
import random
import time
import queue
import traceback

import json
import os
import sys
import pickle


# 配置常量
URL = 'https://patentscope.wipo.int/search/zh/search.jsf'
PAGE_LIMIT = 200

def get_base_dir():
    if getattr(sys, 'frozen', False):
        print(f"Running in bundled mode, base directory: {sys._MEIPASS}")
        return sys._MEIPASS
    print(f"Running in normal mode, base directory: {os.path.dirname(os.path.abspath(__file__))}")
    fp= os.path.dirname(os.path.abspath(__file__))
    print(fp)
    if fp.endswith(".pyz"):
        fp= os.path.dirname(fp)
    return fp

# 获取当前脚本所在的目录
current_dir = get_base_dir()

# 设置文件路径为 dist/wipo_arm 目录
base_dir = current_dir#os.path.dirname(current_dir)  # 获取上级目录
DATA_FILE = os.path.join(base_dir, 'wipo_data.csv')
IPC_LIST_FILE = os.path.join(base_dir, 'wipo_ipcs_list.txt')
STAT_DICT= {"list":[],"idx":0,"task":"ipc"}
if os.path.exists("_tmp_/stat.data"):
    with open("_tmp_/stat.data", "rb") as f:
        STAT_DICT = pickle.load(f)


print(f"Data file path: {DATA_FILE}")
print(f"IPC list file path: {IPC_LIST_FILE}")
with open(IPC_LIST_FILE, 'r') as f:
    ALL_IPC = [i.replace(" ","").replace("\n","") for i in f.readlines()]
if len(STAT_DICT["list"]) == 0:
    STAT_DICT["idx"] = 0
else:
    if "IPC" not in  STAT_DICT or ALL_IPC[STAT_DICT["idx"]-1] !=STAT_DICT["IPC"]:
        print("reset idx", STAT_DICT["idx"],STAT_DICT["IPC"])
        idx=ALL_IPC.index(STAT_DICT["list"][-1])
        STAT_DICT["idx"] =idx
    else:
        STAT_DICT["idx"] -=1
# 创建一个队列，最大大小为10
print("读取所有分类,总数:",len(ALL_IPC),"当前索引位置:",STAT_DICT["idx"])
q = queue.Queue()


# def initialize_web():
#     """初始化网页"""
#     web.get(URL)
#     web.ele('@value=CLASSIF').click()
#     # web.ele('#simpleSearchForm:fpSearch:input').input(get_next_ipc(), clear=True)
#     # time.sleep(30)
#     # web.ele('#simpleSearchForm:fpSearch:buttons').click()
#     time.sleep(10)
#     web.ele('@value=200', -1).click()
#     web.wait.load_start()
#     print('开始爬取')

def save_status():
    """保存状态"""
    with open("_tmp_/stat.data", "wb+") as f:
        pickle.dump(STAT_DICT, f)
def add_ok_ipc(ipc_):
    """记录处理的 IPC"""
    STAT_DICT["list"].append(ipc_)
    save_status()
    with open("data/stat.json", "w+") as f:
        json.dump(STAT_DICT, f)

def get_next_ipc():
    """从 IPC 列表中弹出下一个 IPC"""
    data=ALL_IPC[STAT_DICT["idx"]]
    STAT_DICT["idx"]+=1
    STAT_DICT["IPC"]=data
    if data not in STAT_DICT:
        STAT_DICT[data]={"page":0,"all_page":0}
    save_status()
    return data

def handle_data(html,ipc):
    """处理网页数据"""
    from parsel import Selector
    text = Selector(html)
    eles = text.xpath('//tbody[@id="resultListForm:resultTable_data"]/tr')
    print(f'大小 {len(eles)}')
    try:
        page = text.css('.ps-paginator--page--value').xpath('string(.)').get().replace('\n', '')
    except Exception as e:
        page = "没有数据"
    data_list = []
    for ele in eles:
        name = ele.css('span.ps-patent-result--title--title.content--text-wrap').xpath('string(.)').get().strip() if ele.css('span.ps-patent-result--title--title.content--text-wrap') else ''
        data_rk = ele.css('tr::attr(data-rk)').get()
        data_ri = ele.css('tr::attr(data-ri)').get()
        pubdate = ele.css('div.ps-patent-result--title--ctr-pubdate').xpath('string(.)').get().strip()
        serial_number = ele.css('span.notranslate.ps-patent-result--title--record-number').xpath('string(.)').get().strip() if ele.css('span.notranslate.ps-patent-result--title--record-number') else ''
        detail_url = 'https://patentscope.wipo.int/search/zh/' + ele.css('div.ps-patent-result--first-row a::attr(href)').get() if ele.css('div.ps-patent-result--first-row a') else ''
        # ipc = ele.xpath('.//div[@id="resultListForm:resultTable:0:patentResult"]/@data-mt-ipc').get().strip() if ele.xpath('.//div[@id="resultListForm:resultTable:0:patentResult"]') else ''
        application_number = ele.xpath('.//span[contains(text(), "申请号")]/following-sibling::span').xpath('string(.)').get().strip() if ele.xpath('.//span[contains(text(), "申请号")]/following-sibling::span') else ''
        application_people = ele.xpath('.//span[contains(text(), "申请人")]/following-sibling::span').xpath('string(.)').get().strip() if ele.xpath('.//span[contains(text(), "申请人")]/following-sibling::span') else ''
        inventor = ele.xpath('.//span[contains(text(), "发明人")]/following-sibling::span').xpath('string(.)').get().strip() if ele.xpath('.//span[contains(text(), "发明人")]/following-sibling::span') else ''
        introduction = ele.xpath('.//span[@class="trans-section needTranslation-biblio"]').xpath('string(.)').get().strip() if ele.xpath('.//span[@class="trans-section needTranslation-biblio"]') else ''
        
        data_dict = {
            'name': name,
            'data_rk': data_rk,
            'data_ri': data_ri,
            'ipc': ipc,
            'pubdate': pubdate,
            'serial_number': serial_number,
            'detail_url': detail_url,
            'application_number': application_number,
            'application_people': application_people,
            'inventor': inventor,
            'page': page,
            'introduction': introduction
        }
        print(data_dict)
        data_list.append(data_dict)

    if data_list:
        save_info_data_to_file(data_list,ipc)
    return page

def save_info_data_to_file(data_list,ipc):
    """Save data to a CSV file based on dictionary keys in the list"""
    if not data_list:
        return  # Exit if the list is empty
    fn_name=ipc.replace("/","_")
    with open("data/"+fn_name+".jsonl", 'a+', newline='', encoding='utf-8') as f:
        for d in data_list:
            f.write(json.dumps(d, ensure_ascii=False)+"\n")

def page_init(web,ipc):
    web.goto(URL)
    web.wait_for_load_state('networkidle')
    web.select_option('#simpleSearchForm\\:field\\:input', value="CLASSIF")
    web.fill('#simpleSearchForm\\:fpSearch\\:input', ipc)
    web.click('#simpleSearchForm\\:fpSearch\\:buttons')
    web.wait_for_load_state('networkidle')
    print("double")
    web.click("#resultListCommandsForm\\:viewType\\:input")
    time.sleep(1)
    web.select_option("#resultListCommandsForm\\:viewType\\:input", value="双")  # DOUBLE_VIEW
    web.wait_for_load_state('networkidle')
    print("200")
    web.click("#resultListCommandsForm\\:perPage\\:input")
    time.sleep(1)
    web.select_option("#resultListCommandsForm\\:perPage\\:input", value="200")
    web.wait_for_load_state('networkidle')
def loop_get_page_html():
    """页面爬取"""
    ipc_ = get_next_ipc()
    page_init(web,ipc_)
    if ipc_ in STAT_DICT:#恢复页面
        print(STAT_DICT[ipc_])
        if STAT_DICT[ipc_]['page']<99 and STAT_DICT[ipc_]['page']>2 and STAT_DICT[ipc_]['all_page']>2:
            print(f"恢复: {STAT_DICT[ipc_]['page']}")
            web.click('xpath=//a[@aria-label="单击以转至特定页面"]')
            time.sleep(0.5)
            web.fill("xpath=/html/body/div[2]/div[2]/div/div/div/form/input[2]", str(STAT_DICT[ipc_]['page'] - 1))
            time.sleep(0.5)
            web.click("xpath=/html/body/div[2]/div[2]/div/div/div/form/button")
            time.sleep(1)
            web.wait_for_load_state('networkidle')
    while True:
        if True:
            q.put((web.content(), ipc_), block=False)
            page=0
            all_page=0
            try:
                raw_page = web.query_selector('.ps-paginator--page--value').inner_text().replace('\n', '')
                page = int(raw_page.split("/")[0])
                all_page = int(raw_page.split("/")[1].replace(',', '').replace('，', ''))
                STAT_DICT[ipc_]['page'] = page
                STAT_DICT[ipc_]['all_page'] = all_page
                save_status()
                print(f"生产: {page}")
            except Exception as e:
                print(f'没有数据: {e}')
                
            ele = web.query_selector('xpath=//a[@aria-label="下一页"]')
            if not ele:
                add_ok_ipc(ipc_)
                print('移除')
                print(ipc_)
                print('读取')
                ipc_ = get_next_ipc()
                if not ipc_:
                    print("没有更多 IPC，结束生产者")
                    break
                err_count = 0
                while True:#一直重试
                    try:
                        if not web.url.startswith("https://patentscope.wipo.int/search/zh/result.jsf"):
                            page_init(web, ipc_)
                            break
                        else:
                            web.fill('#advancedSearchForm\\:advancedSearchInput\\:input', ipc_)
                            web.click('#advancedSearchForm\\:advancedSearchInput\\:buttons')
                            web.wait_for_load_state('networkidle')
                            web.select_option("#resultListCommandsForm\\:perPage\\:input", value="200")
                            web.select_option("#resultListCommandsForm\\:viewType\\:input", value="双")  # DOUBLE_VIEW
                            web.wait_for_load_state('networkidle')
                            break
                        time.sleep(0.5)
                    except Exception:
                        traceback.print_exc()
                        err_count+=1
                        if err_count>20:
                            print("搜索失败，尝试重启")
                            os.execl(sys.executable, sys.executable, *sys.argv)
                            exit(0)
                web.wait_for_load_state('networkidle')
            else:
                print("page",page,all_page)
                web.click('xpath=//a[@aria-label="下一页"]')
                web.wait_for_load_state('networkidle')
                if page>0:
                    err_count=0
                    while True:#快速翻页
                        try:
                            new_page = int(
                                web.query_selector('.ps-paginator--page--value').inner_text().replace('\n', '').split(
                                    "/")[0])
                            if new_page != page: break
                            time.sleep(0.3)
                        except Exception as e:
                            err_count+=1
                            traceback.print_exc()
                            if err_count>20:
                                print("翻页失败，尝试重启")
                                os.execl(sys.executable, sys.executable, *sys.argv)
                                exit(0)
                else:
                    web.wait_for_load_state('networkidle')
        else:
            print("队列已满，生产者等待...")
        time.sleep(random.randint(1,10)/10)
    print("已经完成所有任务，请打包交付。")

def page_parser():
    """消费者任务"""
    while True:
        if not q.empty():
            item,ipc = q.get()
            try:
                data_size = handle_data(item,ipc)
                print(f"处理: {data_size} 条数据")
                q.task_done()
            except Exception as e:
                traceback.print_exc()
                print(item)
                continue
        time.sleep(0.1)

def main():
    try:
        from playwright.sync_api import sync_playwright
        from parsel import Selector
    except Exception:
        print("没有安装依赖，安装并重启")
        import subprocess
        subprocess.run([sys.executable, '-m', 'pip', 'install',"-i","https://mirrors.aliyun.com/pypi/simple/ ", 'playwright', 'parsel'])
        subprocess.run([sys.executable, '-m', 'playwright', 'install'])
        subprocess.run([sys.executable, sys.argv[0]])
        exit(0)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        global web
        web = browser.new_page()
        if not os.path.exists("data"):
            os.mkdir("data")
        if not os.path.exists("_tmp_"):
            os.mkdir("_tmp_")
        _thread.start_new_thread(page_parser, ())
        loop_get_page_html()
        browser.close()

if __name__ == '__main__':
    # 初始化网页
    # initialize_web()
    # for i in range(5):
    # print(sys.executable,sys.argv)
    #检查依赖有没有，没有就安装并重启
    main()