# -*- coding: utf-8 -*-
import random
import time
import requests
from dns.qCloud import QcloudApiv3
from dns.aliyun import AliApi
from dns.huawei import HuaWeiApi
from log import Logger
import traceback

# ================= 配置信息 =================
# 说明：因为不再依赖外部商业API，KEY变量可以保持为空或留作备用
KEY = "o1zrmHAF"

# 核心修改：请在此处配置您的 GitHub 用户名和仓库名
GITHUB_USER = "izhadu"       # 替换为您的 GitHub 用户名
GITHUB_REPO = "cf-ddns"      # 替换为您的 仓库名称

# 修改为你需要绑定的域名和子域名。使用 "DEF" 代表全网默认线路轮询。
DOMAINS = {
    "484848.xyz": {
        "@": ["DEF"], 
        "shop": ["DEF"]
    }
}

# 解析生效条数（免费版DNS推荐相同线路最多支持2条解析）
AFFECT_NUM = 2

# DNS服务商选择：1=DNSPod(腾讯云), 2=阿里云, 3=华为云
DNS_SERVER = 1

# 如果使用华为云解析需要填入
REGION_HW = 'cn-east-3'
# 如果使用阿里云解析需要填入
REGION_ALI = 'cn-hongkong'

# 解析生效时间（TTL），普通免费版请勿设置低于600秒
TTL = 600
TYPE = 'v4' # v4 或 v6

# API 密钥配置（建议在GitHub Secrets中配置，此处写死或保留占位符）
SECRETID = 'WTTCWxxxxxxxxxxxxxxxxxxxxx84O0V'
SECRETKEY = 'GXkG6D4X1Nxxxxxxxxxxxxxxxxxxxxx4lRg6lT'

log_cf2dns = Logger('cf2dns.log', level='debug') 

def get_optimization_ip():
    """
    深度优化：从您自己的私有 GitHub 仓库拉取定时更新的 ip.json 优选 IP 列表。
    带有高速 CDN 镜像站点的自动降级兜底逻辑。
    """
    # 策略 1：首选使用 jsDelivr CDN 链接加速读取（国内Actions和VPS环境访问极速且稳定）
    cdn_url = f"https://cdn.jsdelivr.net/gh/{GITHUB_USER}/{GITHUB_REPO}@master/ip.json"
    # 策略 2：备用使用 GitHub Raw 官方原生链接
    raw_url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/master/ip.json"
    
    urls = [cdn_url, raw_url]
    
    for url in urls:
        try:
            log_cf2dns.logger.debug(f"正在尝试从源拉取优选数据: {url}")
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200 or "info" in data:
                    log_cf2dns.logger.info("成功获取到最新的自定义三网优选 IP 接口数据。")
                    return data
            log_cf2dns.logger.warn(f"当前源响应状态码非200: {response.status_code}，尝试下一个。")
        except Exception as e:
            log_cf2dns.logger.warn(f"当前优选源请求异常: {str(e)}，正在切换备份源...")
            
    log_cf2dns.logger.error("【致命错误】所有自定义优选 IP 接口数据源请求均宣告失败，请检查网络或仓库文件。")
    return None

def changeDNS(line_code, s_info, c_info, domain, sub_domain, cloud):
    global AFFECT_NUM, TYPE
    recordType = "AAAA" if TYPE == 'v6' else "A"

    lines_map = {"CM": "移动", "CU": "联通", "CT": "电信", "AB": "境外", "DEF": "默认"}
    line_name = lines_map.get(line_code, "默认")

    try:
        create_num = AFFECT_NUM - len(s_info)
        if create_num == 0:
            for info in s_info:
                if len(c_info) == 0:
                    break
                cf_ip = c_info.pop(random.randint(0, len(c_info) - 1))["ip"]
                if cf_ip in str(s_info):
                    continue
                ret = cloud.change_record(domain, info["recordId"], sub_domain, cf_ip, recordType, line_name, TTL)
                if DNS_SERVER != 1 or ret.get("code") == 0:
                    log_cf2dns.logger.info(f"更新 DNS 成功: 域名: {sub_domain}.{domain} | 线路: {line_name} | IP: {cf_ip}")
                else:
                    log_cf2dns.logger.error(f"更新 DNS 失败: 域名: {sub_domain}.{domain} | 错误信息: {ret.get('message')}")
                    
        elif create_num > 0:
            for _ in range(create_num):
                if len(c_info) == 0:
                    break
                cf_ip = c_info.pop(random.randint(0, len(c_info) - 1))["ip"]
                if cf_ip in str(s_info):
                    continue
                ret = cloud.create_record(domain, sub_domain, cf_ip, recordType, line_name, TTL)
                if DNS_SERVER != 1 or ret.get("code") == 0:
                    log_cf2dns.logger.info(f"创建 DNS 成功: 域名: {sub_domain}.{domain} | 线路: {line_name} | IP: {cf_ip}")
                else:
                    log_cf2dns.logger.error(f"创建 DNS 失败: 域名: {sub_domain}.{domain} | 错误信息: {ret.get('message')}")
        else:
            for info in s_info:
                if create_num == 0 or len(c_info) == 0:
                    break
                cf_ip = c_info.pop(random.randint(0, len(c_info) - 1))["ip"]
                if cf_ip in str(s_info):
                    create_num += 1
                    continue
                ret = cloud.change_record(domain, info["recordId"], sub_domain, cf_ip, recordType, line_name, TTL)
                if DNS_SERVER != 1 or ret.get("code") == 0:
                    log_cf2dns.logger.info(f"覆盖 DNS 成功: 域名: {sub_domain}.{domain} | 线路: {line_name} | IP: {cf_ip}")
                else:
                    log_cf2dns.logger.error(f"覆盖 DNS 失败: 域名: {sub_domain}.{domain} | 错误信息: {ret.get('message')}")
                create_num += 1
    except Exception as e:
        log_cf2dns.logger.error(f"DNS解析变更处理中捕获异常: {str(e)}")

def main(cloud):
    global AFFECT_NUM, TYPE
    recordType = "AAAA" if TYPE == 'v6' else "A"
    
    if len(DOMAINS) <= 0:
        return

    try:
        cfips = get_optimization_ip()
        if cfips is None:
            return
            
        # 安全读取各线路IP资源池，添加兜底防崩溃处理
        info_pool = cfips.get("info", {})
        cf_cmips = info_pool.get("CM", [])
        cf_cuips = info_pool.get("CU", [])
        cf_ctips = info_pool.get("CT", [])
        cf_abips = info_pool.get("AB", cf_ctips)   # 如果没有AB，默认用CT兜底
        cf_defips = info_pool.get("DEF", cf_ctips) # 如果没有DEF，默认用CT兜底

        for domain, sub_domains in DOMAINS.items():
            for sub_domain, lines in sub_domains.items():
                temp_cf_cmips = cf_cmips.copy()
                temp_cf_cuips = cf_cuips.copy()
                temp_cf_ctips = cf_ctips.copy()
                temp_cf_abips = cf_abips.copy()
                temp_cf_defips = cf_defips.copy()
                
                # 如果是 DNSPod，先清理掉潜在冲突的老旧 CNAME 记录
                if DNS_SERVER == 1:
                    ret = cloud.get_record(domain, 20, sub_domain, "CNAME")
                    if ret.get("code") == 0:
                        for record in ret["data"]["records"]:
                            if record["line"] in ["移动", "联通", "电信", "默认", "境外"]:
                                cloud.del_record(domain, record["id"])
                                log_cf2dns.logger.info(f"已清理历史冲突 CNAME 解析记录: {sub_domain}.{domain} [{record['line']}]")

                # 获取当前已生效的解析
                ret = cloud.get_record(domain, 100, sub_domain, recordType)
                if DNS_SERVER != 1 or ret.get("code") == 0:
                    if DNS_SERVER == 1 and "Free" in ret.get("data", {}).get("domain", {}).get("grade", "") and AFFECT_NUM > 2:
                        AFFECT_NUM = 2
                        
                    cm_info, cu_info, ct_info, ab_info, def_info = [], [], [], [], []
                    records_list = ret.get("data", {}).get("records", []) if DNS_SERVER == 1 else ret.get("records", [])
                    
                    for record in records_list:
                        info = {"recordId": record["id"], "value": record["value"]}
                        if record["line"] == "移动":
                            cm_info.append(info)
                        elif record["line"] == "联通":
                            cu_info.append(info)
                        elif record["line"] == "电信":
                            ct_info.append(info)
                        elif record["line"] == "境外":
                            ab_info.append(info)
                        elif record["line"] == "默认":
                            def_info.append(info)

                    # 遍历并处理配置的各条目标线路
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
        traceback.print_exc()  
        log_cf2dns.logger.error(f"核心同步引擎崩溃异常: {str(e)}")

if __name__ == '__main__':
    if DNS_SERVER == 1:
        cloud = QcloudApiv3(SECRETID, SECRETKEY)
    elif DNS_SERVER == 2:
        cloud = AliApi(SECRETID, SECRETKEY, REGION_ALI)
    elif DNS_SERVER == 3:
        cloud = HuaWeiApi(SECRETID, SECRETKEY, REGION_HW)
    main(cloud)