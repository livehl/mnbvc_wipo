import threading
import time
import queue
from DrissionPage import ChromiumPage
from parsel import Selector
import json
import os
from concurrent.futures import ThreadPoolExecutor
import sys
import csv

# 配置常量
DEFAULT_IPC = 'A23P20/17'
URL = 'https://patentscope.wipo.int/search/zh/search.jsf'
PAGE_LIMIT = 200

def get_base_dir():
    if getattr(sys, 'frozen', False):
        print(f"Running in bundled mode, base directory: {sys._MEIPASS}")
        return sys._MEIPASS
    print(f"Running in normal mode, base directory: {os.path.dirname(os.path.abspath(__file__))}")
    return os.path.dirname(os.path.abspath(__file__))

# 获取当前脚本所在的目录
current_dir = get_base_dir()

# 设置文件路径为 dist/wipo_arm 目录
base_dir = os.path.dirname(current_dir)  # 获取上级目录
LOG_FILE = os.path.join(base_dir, 'wipo_ipcs_list_logs.txt')
DATA_FILE = os.path.join(base_dir, 'wipo_data.csv')
IPC_LIST_FILE = os.path.join(base_dir, 'wipo_ipcs_list.txt')

print(f"Log file path: {LOG_FILE}")
print(f"Data file path: {DATA_FILE}")
print(f"IPC list file path: {IPC_LIST_FILE}")

# 创建一个队列，最大大小为5
q = queue.Queue(maxsize=5)
web = ChromiumPage()

def get_last_ipc():
    """从文件中读取最后处理的 IPC"""
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            lines = f.readlines()
            if lines:
                return lines[-1].strip().replace(' ', '')  # 返回最后一行 IPC
    return None

def initialize_web():
    """初始化网页"""
    web.get(URL)
    web.ele('@value=CLASSIF').click()
    web.ele('#simpleSearchForm:fpSearch:input').input(get_last_ipc() or DEFAULT_IPC, clear=True)
    web.ele('#simpleSearchForm:fpSearch:buttons').click()
    time.sleep(5)
    web.ele('@value=200', -1).click()
    web.wait.load_start()
    print('开始爬取')

def add_to_logs(ipc_):
    """记录处理的 IPC"""
    with open(LOG_FILE, 'a') as f:
        f.write(ipc_ + '\n')

def remove_from_logs(ipc_):
    """从日志中移除 IPC"""
    # 检查日志文件是否存在，如果不存在则创建一个空文件
    if not os.path.exists(LOG_FILE):
        print(f"日志文件不存在，正在创建: {LOG_FILE}")
        with open(LOG_FILE, 'w') as f:
            f.write('')  # 创建一个空文件
    with open(LOG_FILE, 'r') as f:
        lines = f.readlines()
    with open(LOG_FILE, 'w') as f:
        f.writelines([line for line in lines if line.strip() != ipc_])

def pop_from_list():
    """从 IPC 列表中弹出下一个 IPC"""
    if os.path.exists(IPC_LIST_FILE):
        with open(IPC_LIST_FILE, 'r') as f:
            lines = f.readlines()
        if lines:
            ipc_ = lines[0].strip()
            with open(IPC_LIST_FILE, 'w') as f:
                f.writelines(lines[1:])
            return ipc_
    return None

def handle_data(html):
    """处理网页数据"""
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
        ipc = ele.xpath('.//div[@id="resultListForm:resultTable:0:patentResult"]/@data-mt-ipc').get().strip() if ele.xpath('.//div[@id="resultListForm:resultTable:0:patentResult"]') else ''
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

    # if data_list:
        # save_data_to_file(data_list)
    return page

def save_data_to_file(data_list):
    """Save data to a CSV file based on dictionary keys in the list"""
    if not data_list:
        return  # Exit if the list is empty

    file_exists = os.path.exists(DATA_FILE)

    # Use the keys from the first dictionary as the fieldnames for the CSV file
    fieldnames = data_list[0].keys()

    # Open the CSV file in append mode and write rows
    with open(DATA_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        # Write the header only if the file is new
        if not file_exists:
            writer.writeheader()

        # Write each dictionary in the list as a row in the CSV file
        writer.writerows(data_list)

def producer():
    """生产者任务"""
    ipc_ = get_last_ipc() or DEFAULT_IPC
    while True:
        if not q.full():
            q.put(web.html)
            try:
                page = web.ele('.ps-paginator--page--value').raw_text.replace('\n', '')
                print(f"生产: {page}")
            except Exception as e:
                print(f'没有数据: {e}')
                
            ele = web.ele('xpath://a[@aria-label="下一页"]', timeout=5)
            if not ele:
                print('移除')
                print(ipc_)
                remove_from_logs(ipc_)
                print('读取')
                ipc_ = pop_from_list()
                if not ipc_:
                    print("没有更多 IPC，结束生产者")
                    break
                add_to_logs(ipc_)
                web.ele('#advancedSearchForm:advancedSearchInput:input').input('IC:(' + ipc_.replace(' ', '') + ')', clear=True, by_js=True)
                web.ele('#advancedSearchForm:advancedSearchInput:buttons').click()
                web.wait.load_start()
            else:
                ele.click()
                web.wait.load_start()
        else:
            print("队列已满，生产者等待...")
        time.sleep(2)

def consumer():
    """消费者任务"""
    while True:
        if not q.empty():
            item = q.get()
            data_size = handle_data(item)
            print(f"消费: {data_size} 条数据")
            q.task_done()
        else:
            print("队列已空，消费者等待...")
        time.sleep(5)

if __name__ == '__main__':
    # 初始化网页
    initialize_web()

    # 使用线程池执行生产者和消费者任务
    with ThreadPoolExecutor(max_workers=2) as executor:
        executor.submit(producer)
        executor.submit(consumer)