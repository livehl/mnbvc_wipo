import threading
import time
import queue
from DrissionPage import ChromiumPage
from parsel import Selector
import json
import os
from concurrent.futures import ThreadPoolExecutor
import sys

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
DATA_FILE = os.path.join(base_dir, 'wipo_data.json')
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
    
    data_list = []
    for ele in eles:
        name = ele.css('span.ps-patent-result--title--title.content--text-wrap').xpath('string(.)').get().strip() if ele.css('span.ps-patent-result--title--title.content--text-wrap') else ''
        serial_number = ele.css('span.notranslate.ps-patent-result--title--record-number').xpath('string(.)').get().strip() if ele.css('span.notranslate.ps-patent-result--title--record-number') else ''
        detail_url = 'https://patentscope.wipo.int/search/zh/' + ele.css('div.ps-patent-result--first-row a::attr(href)').get() if ele.css('div.ps-patent-result--first-row a') else ''
        
        data_dict = {
            'name': name,
            'serial_number': serial_number,
            'detail_url': detail_url,
        }
        data_list.append(data_dict)

    save_data_to_file(data_list)
    return len(data_list)

def save_data_to_file(data_list):
    """将数据保存到文件"""
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w') as f:
            json.dump([], f)
    with open(DATA_FILE, 'r+') as f:
        file_data = json.load(f)
        file_data.extend(data_list)
        f.seek(0)
        json.dump(file_data, f, ensure_ascii=False)

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