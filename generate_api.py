import json
import os

def txt_to_json():
    bestcf_file = "bestcf.txt"
    bestproxy_file = "bestproxy.txt"
    
    cf_ips = []
    proxy_ips = []

    # 读取 bestcf.txt 的 IP
    if os.path.exists(bestcf_file):
        with open(bestcf_file, "r", encoding="utf-8") as f:
            cf_ips = [{"ip": line.strip()} for line in f if line.strip() and not line.startswith("IP")]

    # 读取 bestproxy.txt 的 IP
    if os.path.exists(bestproxy_file):
        with open(bestproxy_file, "r", encoding="utf-8") as f:
            proxy_ips = [{"ip": line.strip()} for line in f if line.strip() and not line.startswith("IP")]

    # 组装为 cf-ddns 需要的 JSON 格式
    api_data = {
        "code": 200,
        "info": {
            "CM": cf_ips,       # 移动
            "CU": cf_ips,       # 联通
            "CT": cf_ips,       # 电信
            "AB": cf_ips,       # 境外
            "DEF": cf_ips,      # 默认
            "PROXY": proxy_ips  # 代理节点 IP
        }
    }

    with open("ip.json", "w", encoding="utf-8") as f:
        json.dump(api_data, f, indent=4, ensure_ascii=False)
    
    print("成功生成 ip.json 接口文件！")

if __name__ == "__main__":
    txt_to_json()