# Mail: tongdongdong@outlook.com
import random
import time
import json
import requests
import os
import traceback
import sys

from dns.qCloud import QcloudApiv3 
from dns.aliyun import AliApi
from dns.huawei import HuaWeiApi

# ================= 新增核心模式控制变量 =================
# True : 强力精简模式（只同步默认 DEF 线路，全自动清空残留的移动/联通/电信分线路记录）
# False: 传统多线路模式（严格按照你在 GitHub Secrets 里的 DOMAINS 分线路配置进行独立更新）
ONLY_DEFAULT = os.environ.get("ONLY_DEFAULT", "True").lower() == "true"
# =======================================================

# 可以从https://shop.hostmonit.com获取
KEY = os.environ.get("KEY", "")  
# CM:移动 CU:联通 CT:电信 AB:境外 DEF:默认
DOMAINS = json.loads(os.environ.get("DOMAINS", "{}"))  
# 腾讯云后台获取 https://console.cloud.tencent.com/cam/capi
SECRETID = os.environ.get("SECRETID", "")  
SECRETKEY = os.environ.get("SECRETKEY", "")  

# 默认为普通版本 不用修改
AFFECT_NUM = 2
# DNS服务商 1:DNSPod, 2:阿里云, 3:华为云
DNS_SERVER = 1
# 华为云解析 REGION
REGION_HW = 'cn-east-3'
# 阿里云解析 REGION 
REGION_ALI = 'cn-hongkong'

# 解析生效时间
TTL = 600

# v4为筛选出IPv4的IP  v6为筛选出IPv6的IP
if len(sys.argv) >= 2:
    RECORD_TYPE = sys.argv[1]
else:
    RECORD_TYPE = "A"


def get_optimization_ip():
    """从本地闭环生成的 ip.json 获取优选池"""
    try:
        if os.path.exists('ip.json'):
            with open('ip.json', 'r', encoding='utf-8') as f:
                print("成功读取到本地闭环生成的优选 IP 接口数据。")
                return json.load(f)
        else:
            print("CHANGE OPTIMIZATION IP ERROR: 本地 ip.json 文件未找到。")
            return None
    except Exception as e:
        print("CHANGE OPTIMIZATION IP ERROR: " + str(e))
        return None

def changeDNS(line, s_info, c_info, domain, sub_domain, cloud):
    global AFFECT_NUM, RECORD_TYPE

    lines = {"CM": "移动", "CU": "联通", "CT": "电信", "AB": "境外", "DEF": "默认"}
    line = lines[line]

    try:
        create_num = AFFECT_NUM - len(s_info)
        if create_num == 0:
            for info in s_info:
                if len(c_info) == 0:
                    break
                cf_ip = c_info.pop(random.randint(0, len(c_info)-1))["ip"]
                if cf_ip in str(s_info):
                    continue
                ret = cloud.change_record(domain, info["recordId"], sub_domain, cf_ip, RECORD_TYPE, line, TTL)
                if DNS_SERVER != 1 or ret["code"] == 0:
                    print(f"CHANGE DNS SUCCESS: ----Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}----DOMAIN: {domain}----SUBDOMAIN: {sub_domain}----RECORDLINE: {line}----RECORDID: {info['recordId']}----VALUE: {cf_ip}")
                else:
                    print(f"CHANGE DNS ERROR: ----Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}----DOMAIN: {domain}----SUBDOMAIN: {sub_domain}----RECORDLINE: {line}----RECORDID: {info['recordId']}----VALUE: {cf_ip}----MESSAGE: {ret['message']}")
        elif create_num > 0:
            for i in range(create_num):
                if len(c_info) == 0:
                    break
                cf_ip = c_info.pop(random.randint(0, len(c_info)-1))["ip"]
                if cf_ip in str(s_info):
                    continue
                ret = cloud.create_record(domain, sub_domain, cf_ip, RECORD_TYPE, line, TTL)
                if DNS_SERVER != 1 or ret["code"] == 0:
                    print(f"CREATE DNS SUCCESS: ----Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}----DOMAIN: {domain}----SUBDOMAIN: {sub_domain}----RECORDLINE: {line}----VALUE: {cf_ip}")
                else:
                    print(f"CREATE DNS ERROR: ----Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}----DOMAIN: {domain}----SUBDOMAIN: {sub_domain}----RECORDLINE: {line}----VALUE: {cf_ip}----MESSAGE: {ret.get('message', 'Unknown Error')}")
        else:
            for info in s_info:
                if create_num == 0 or len(c_info) == 0:
                    break
                cf_ip = c_info.pop(random.randint(0, len(c_info)-1))["ip"]
                if cf_ip in str(s_info):
                    create_num += 1
                    continue
                ret = cloud.change_record(domain, info["recordId"], sub_domain, cf_ip, RECORD_TYPE, line, TTL)
                if DNS_SERVER != 1 or ret["code"] == 0:
                    print(f"CHANGE DNS SUCCESS: ----Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}----DOMAIN: {domain}----SUBDOMAIN: {sub_domain}----RECORDLINE: {line}----RECORDID: {info['recordId']}----VALUE: {cf_ip}")
                else:
                    print(f"CHANGE DNS ERROR: ----Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}----DOMAIN: {domain}----SUBDOMAIN: {sub_domain}----RECORDLINE: {line}----RECORDID: {info['recordId']}----VALUE: {cf_ip}----MESSAGE: {ret['message']}")
                create_num += 1
    except Exception as e:
            print(f"CHANGE DNS ERROR: ----Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}----MESSAGE: {traceback.format_exc()}")

def main(cloud):
    global AFFECT_NUM, RECORD_TYPE, ONLY_DEFAULT
    if len(DOMAINS) > 0:
        try:
            cfips = get_optimization_ip()
            if cfips is None or cfips.get("code") != 200:
                print(f"GET CLOUDFLARE IP ERROR: ----Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
                return
            
            if ONLY_DEFAULT:
                # ================= 模式 1: 仅更新全网默认线路 =================
                print("⚠️ [当前运行模式]: 仅更新【默认(DEF)】线路，自动清理其余分线路记录。")
                cf_defips = cfips["info"].get("DEF", cfips["info"].get("CT", []))
                
                for domain, sub_domains in DOMAINS.items():
                    for sub_domain, _ in sub_domains.items():
                        temp_cf_defips = cf_defips.copy()
                        
                        if DNS_SERVER == 1:
                            ret = cloud.get_record(domain, 20, sub_domain, "CNAME")
                            if ret["code"] == 0:
                                for record in ret["data"]["records"]:
                                    if record["line"] in ["移动", "联通", "电信", "默认"]:
                                        cloud.del_record(domain, record["id"])
                        
                        ret = cloud.get_record(domain, 100, sub_domain, RECORD_TYPE)
                        if DNS_SERVER != 1 or ret["code"] == 0:
                            if DNS_SERVER == 1 and "Free" in ret["data"]["domain"]["grade"] and AFFECT_NUM > 2:
                                AFFECT_NUM = 2
                                
                            def_info = []
                            for record in ret["data"]["records"]:
                                if record["line"] in ["移动", "联通", "电信"]:
                                    print(f"🧹 顺手清理老旧线路记录: {sub_domain}.{domain} [{record['line']}] -> {record['value']}")
                                    cloud.del_record(domain, record["id"])
                                elif record["line"] == "默认":
                                    def_info.append({"recordId": record["id"], "value": record["value"]})
                            
                            print(f"🚀 正在将最新优选 IP 同步至【默认】线路...")
                            changeDNS("DEF", def_info, temp_cf_defips, domain, sub_domain, cloud)
            else:
                # ================= 模式 2: CU / CM / CT 分开独立更新 =================
                print("🌐 [当前运行模式]: 三网多线路独立切分更新。")
                cf_cmips = cfips["info"].get("CM", [])
                cf_cuips = cfips["info"].get("CU", [])
                cf_ctips = cfips["info"].get("CT", [])
                
                for domain, sub_domains in DOMAINS.items():
                    for sub_domain, lines in sub_domains.items():
                        temp_cf_cmips = cf_cmips.copy()
                        temp_cf_cuips = cf_cuips.copy()
                        temp_cf_ctips = cf_ctips.copy()
                        temp_cf_abips = cf_ctips.copy()
                        temp_cf_defips = cf_ctips.copy()
                        
                        if DNS_SERVER == 1:
                            ret = cloud.get_record(domain, 20, sub_domain, "CNAME")
                            if ret["code"] == 0:
                                for record in ret["data"]["records"]:
                                    if record["line"] in ["移动", "联通", "电信"]:
                                        cloud.del_record(domain, record["id"])
                        
                        ret = cloud.get_record(domain, 100, sub_domain, RECORD_TYPE)
                        if DNS_SERVER != 1 or ret["code"] == 0:
                            if DNS_SERVER == 1 and "Free" in ret["data"]["domain"]["grade"] and AFFECT_NUM > 2:
                                AFFECT_NUM = 2
                                
                            cm_info, cu_info, ct_info, ab_info, def_info = [], [], [], [], []
                            line_mapping = {
                                "移动": cm_info, "联通": cu_info, "电信": ct_info, 
                                "境外": ab_info, "默认": def_info
                            }
                            
                            for record in ret["data"]["records"]:
                                if record["line"] in line_mapping:
                                    line_mapping[record["line"]].append({
                                        "recordId": record["id"], 
                                        "value": record["value"]
                                    })

                            for line in lines:
                                if line == "CM":
                                    changeDNS("CM", cm_info, temp_cf_cmips, domain, sub_domain, cloud)
                                elif line == "CU":
                                    changeDNS("CU", cu_info, temp_cf_cuips, domain, sub_domain, cloud)
                                elif line == "CT":
                                    changeDNS("CT", ct_info, temp_cf_ctips, domain, sub_domain, cloud)
                                elif line == "AB":
                                    changeDNS("AB", ab_info, temp_cf_abips, domain, sub_domain, cloud)
                                elif line == "DEF":
                                    changeDNS("DEF", def_info, temp_cf_defips, domain, sub_domain, cloud)
        except Exception as e:
            print(f"CHANGE DNS ERROR: ----Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}----MESSAGE: {traceback.format_exc()}")

if __name__ == '__main__':
    if DNS_SERVER == 1:
        cloud = QcloudApiv3(SECRETID, SECRETKEY)
    elif DNS_SERVER == 2:
        cloud = AliApi(SECRETID, SECRETKEY, REGION_ALI)
    elif DNS_SERVER == 3:
        cloud = HuaWeiApi(SECRETID, SECRETKEY, REGION_HW)
    main(cloud)