import json
from pathlib import Path

entries = []

def add(school, code, url, stype, source="webfetch_official"):
    entries.append({
        "school_name": school,
        "school_code": code,
        "candidate_url": url,
        "system_type": stype,
        "source": source,
    })

wust = "武汉科技大学"
wust_code = "4142010488"
add(wust, wust_code, "https://portal.wust.edu.cn", "unified_portal")
add(wust, wust_code, "https://zhxxw.wust.edu.cn", "other")
add(wust, wust_code, "http://mail.wust.edu.cn/", "other")
add(wust, wust_code, "https://en.wust.edu.cn/", "other")
add(wust, wust_code, "https://jwc.wust.edu.cn/", "academic_department_website")
add(wust, wust_code, "https://ysxy.wust.edu.cn/", "graduate_system")
add(wust, wust_code, "https://jxjyxy.wust.edu.cn/", "continuing_education_system")
add(wust, wust_code, "https://pgb.wust.edu.cn/", "other")
add(wust, wust_code, "https://kjc.wust.edu.cn/kyzc.htm", "research_system")
add(wust, wust_code, "http://zs.wust.edu.cn/#/index", "admission_website")
add(wust, wust_code, "https://wust.91wllm.cn", "other")
add(wust, wust_code, "https://wustyjs.91wllm.cn/", "other")
add(wust, wust_code, "https://rsc.wust.edu.cn/", "other")
add(wust, wust_code, "https://rsc.wust.edu.cn/cpyc/zpxx.htm", "other")
add(wust, wust_code, "https://xxgk.wust.edu.cn/", "other")
add(wust, wust_code, "https://ehall.wust.edu.cn/taskcenter/workflow/index", "unified_portal")
add(wust, wust_code, "https://oa.wust.edu.cn/seeyon/wust/sso.do", "other")
add(wust, wust_code, "http://bkjx.wust.edu.cn/jsxsd/sso.jsp", "edu_system")
add(wust, wust_code, "https://wkdzcsp.wust.edu.cn/dlpt/login.aspx", "other")
add(wust, wust_code, "https://news.wust.edu.cn/", "other")
add(wust, wust_code, "https://xyh.wust.edu.cn/xyh/xyfc.htm", "other")

upc = "中国石油大学（华东）"
upc_code = "4137010425"
add(upc, upc_code, "https://i.upc.edu.cn", "unified_portal")
add(upc, upc_code, "https://service.upc.edu.cn", "unified_portal")
add(upc, upc_code, "https://library.upc.edu.cn/", "other")
add(upc, upc_code, "http://xzxx.upc.edu.cn/", "other")
add(upc, upc_code, "http://rsc.upc.edu.cn/2315/list.htm", "other")
add(upc, upc_code, "http://fund.upc.edu.cn/", "other")
add(upc, upc_code, "http://mail.upc.edu.cn/", "other")
add(upc, upc_code, "http://english.upc.edu.cn/", "other")
add(upc, upc_code, "http://jwc.upc.edu.cn/", "academic_department_website")
add(upc, upc_code, "http://gs.upc.edu.cn/", "graduate_system")
add(upc, upc_code, "https://cie.upc.edu.cn/", "international_system")
add(upc, upc_code, "http://jyfz.upc.edu.cn/", "continuing_education_system")
add(upc, upc_code, "http://kjc.upc.edu.cn/", "research_system")
add(upc, upc_code, "http://wkc.upc.edu.cn/", "other")
add(upc, upc_code, "http://rsc.upc.edu.cn/", "other")
add(upc, upc_code, "http://finance.upc.edu.cn/", "other")
add(upc, upc_code, "https://zbb.upc.edu.cn", "other")
add(upc, upc_code, "http://io.upc.edu.cn/", "international_system")
add(upc, upc_code, "http://hfc.upc.edu.cn/", "other")
add(upc, upc_code, "https://zhaosheng.upc.edu.cn", "admission_website")
add(upc, upc_code, "https://yz.upc.edu.cn/", "admission_website")
add(upc, upc_code, "https://career.upc.edu.cn/", "other")
add(upc, upc_code, "http://cie.upc.edu.cn/admission_cn/", "admission_website")
add(upc, upc_code, "http://upol.upc.edu.cn/", "continuing_education_system")
add(upc, upc_code, "http://sdlx.upc.edu.cn/", "other")
add(upc, upc_code, "http://xyh.upc.edu.cn/", "other")
add(upc, upc_code, "http://xxgk.upc.edu.cn/", "other")
add(upc, upc_code, "https://jwxt.upc.edu.cn/jsxsd/sso.jsp", "edu_system")
add(upc, upc_code, "https://webvpn.upc.edu.cn", "other")
add(upc, upc_code, "https://learn.upc.edu.cn/meol//index.do", "other")
add(upc, upc_code, "https://sydxb.upc.edu.cn", "other")
add(upc, upc_code, "https://news.upc.edu.cn/", "other")
add(upc, upc_code, "https://journal.upc.edu.cn/", "other")
add(upc, upc_code, "http://dag.upc.edu.cn/", "other")

hebau = "河北农业大学"
hebau_code = "4113010086"
add(hebau, hebau_code, "http://oa.hebau.edu.cn/", "other")
add(hebau, hebau_code, "https://ehall.hebau.edu.cn/", "unified_portal")
add(hebau, hebau_code, "http://mail.hebau.edu.cn/", "other")
add(hebau, hebau_code, "https://english.hebau.edu.cn/index.htm", "other")
add(hebau, hebau_code, "https://jiaowu.hebau.edu.cn/", "academic_department_website")
add(hebau, hebau_code, "https://yanjiusheng.hebau.edu.cn/", "graduate_system")
add(hebau, hebau_code, "https://guojihezuo.hebau.edu.cn/index.htm", "international_system")
add(hebau, hebau_code, "https://chengjiao.hebau.edu.cn/", "continuing_education_system")
add(hebau, hebau_code, "https://nongfa.hebau.edu.cn/", "other")
add(hebau, hebau_code, "https://xkxw.hebau.edu.cn/xkjs.htm", "other")
add(hebau, hebau_code, "https://zhaosheng.hebau.edu.cn/", "admission_website")
add(hebau, hebau_code, "https://yanjiusheng.hebau.edu.cn/zsxx.htm", "admission_website")
add(hebau, hebau_code, "https://jiuye.hebau.edu.cn/", "other")
add(hebau, hebau_code, "http://urp.hebau.edu.cn:1009/jwapp/sys/homeapp/index.do", "edu_system")
add(hebau, hebau_code, "https://yjsh.hebau.edu.cn/", "graduate_system")
add(hebau, hebau_code, "http://lib.hebau.edu.cn/", "other")
add(hebau, hebau_code, "http://qks.hebau.edu.cn/", "other")
add(hebau, hebau_code, "http://wlzx.hebau.edu.cn/", "other")
add(hebau, hebau_code, "https://xczhx.hebau.edu.cn/", "other")
add(hebau, hebau_code, "http://xxgk.hebau.edu.cn/", "other")
add(hebau, hebau_code, "http://zhbcg.hebau.edu.cn/", "other")
add(hebau, hebau_code, "https://www.hebau.edu.cn/xyh/", "other")

out = Path("data/discovery_batches/batch_152.json")
out.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"wrote {len(entries)} entries to {out}")