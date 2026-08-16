import json
from pathlib import Path

entries = []

def add(school, code, url, st, note=""):
    entries.append({
        "school_name": school,
        "school_code": code,
        "candidate_url": url,
        "system_type": st,
        "source": "webfetch_official",
        "source_note": note,
    })

syu = "沈阳大学"; syu_c = "4121011035"
add(syu, syu_c, "https://one.syu.edu.cn", "unified_portal", "师生服务中心")
add(syu, syu_c, "https://oa.syu.edu.cn", "oa_system", "OA系统")
add(syu, syu_c, "http://yjs.syu.edu.cn/", "graduate_system", "研究生教育")
add(syu, syu_c, "http://wsc.syu.edu.cn", "international_system", "留学生教育/国际交流")
add(syu, syu_c, "http://syuzsjy.syu.edu.cn", "admission_website", "本科生招生")
add(syu, syu_c, "http://zyfzzd.syu.edu.cn", "career_website", "就业工作")
add(syu, syu_c, "http://hzfzc.syu.edu.cn", "alumni_website", "合作发展处/校友会")
add(syu, syu_c, "http://rsc.syu.edu.cn/", "hr_website", "师资/人才招聘")
add(syu, syu_c, "http://lib.syu.edu.cn", "library", "图书馆")
add(syu, syu_c, "http://mail.syu.edu.cn/", "email", "邮箱")
add(syu, syu_c, "http://archives.syu.edu.cn/", "archives", "校史馆")
add(syu, syu_c, "http://museum.syu.edu.cn/", "museum", "自然博物馆")

henu = "河南大学"; henu_c = "4141010475"
add(henu, henu_c, "https://ehall.henu.edu.cn/", "unified_portal", "网上办事大厅")
add(henu, henu_c, "https://ehall.henu.edu.cn/ywtb-portal/standard/index.html#/hall", "unified_portal", "学生/教职工门户")
add(henu, henu_c, "http://oa.henu.edu.cn/", "oa_system", "办公系统")
add(henu, henu_c, "https://jwc.henu.edu.cn/", "academic_department_website", "本科生教育/教务处")
add(henu, henu_c, "https://grs.henu.edu.cn/", "graduate_system", "研究生教育")
add(henu, henu_c, "https://dwhy.henu.edu.cn/", "international_system", "留学生教育")
add(henu, henu_c, "https://yjy.henu.edu.cn/", "continuing_education_system", "继续教育")
add(henu, henu_c, "https://zs.henu.edu.cn/", "admission_website", "本科生招生")
add(henu, henu_c, "https://job.henu.edu.cn/", "career_website", "就业指导")
add(henu, henu_c, "https://stu.henu.edu.cn/", "student_affairs", "学生工作部")
add(henu, henu_c, "https://rsc.henu.edu.cn/rczp.htm", "hr_website", "人才招聘")
add(henu, henu_c, "https://iao.henu.edu.cn/", "international_system", "国际合作与交流处")
add(henu, henu_c, "https://kyc.henu.edu.cn/xswyh.htm", "academic_committee", "学术委员会")
add(henu, henu_c, "https://lib.henu.edu.cn/", "library", "图书馆")
add(henu, henu_c, "https://xyh.henu.edu.cn/", "alumni_website", "校友会")
add(henu, henu_c, "https://news.henu.edu.cn/", "news", "新闻网")
add(henu, henu_c, "https://hupress.henu.edu.cn/", "press", "图书出版")
add(henu, henu_c, "https://ist.henu.edu.cn/", "international_system", "国际欧美理工学院")
add(henu, henu_c, "https://oy.henu.edu.cn/", "international_system", "欧亚国际学院")
add(henu, henu_c, "https://aiihu.henu.edu.cn/index.htm", "international_system", "阿斯顿国际学院")
add(henu, henu_c, "https://jjs.henu.edu.cn/", "other", "清廉河大")
add(henu, henu_c, "https://wmw.henu.edu.cn/", "other", "文明创建")
add(henu, henu_c, "https://xxgk.henu.edu.cn/index.htm", "other", "信息公开")

hnust = "湖南科技大学"; hnust_c = "4143010534"
add(hnust, hnust_c, "https://i.hnust.edu.cn/", "unified_portal", "融合门户")
add(hnust, hnust_c, "https://jwc.hnust.edu.cn/", "academic_department_website", "本科生教育/教务处")
add(hnust, hnust_c, "https://graduate.hnust.edu.cn/", "graduate_system", "研究生教育")
add(hnust, hnust_c, "https://jxjyxy.hnust.edu.cn/", "continuing_education_system", "继续教育")
add(hnust, hnust_c, "https://dwll.hnust.edu.cn/", "international_system", "国际学生教育")
add(hnust, hnust_c, "https://kyfw.hnust.edu.cn/userAction!do_casLogin.action", "research_system", "科研系统/金智")
add(hnust, hnust_c, "https://science.hnust.edu.cn/kycg/index.htm", "research_system", "科研成果")
add(hnust, hnust_c, "https://zscq.hnust.edu.cn/", "other", "成果转化")
add(hnust, hnust_c, "https://qks.hnust.edu.cn/", "other", "学术期刊")
add(hnust, hnust_c, "https://zs.hnust.edu.cn/", "admission_website", "本科生招生")
add(hnust, hnust_c, "https://jy.hnust.edu.cn/", "career_website", "就业服务")
add(hnust, hnust_c, "https://cxcyxy.hnust.edu.cn/", "other", "创新创业")
add(hnust, hnust_c, "https://xyyhzb.hnust.edu.cn/", "alumni_website", "校友/捐赠")
add(hnust, hnust_c, "https://webvpn.hnust.edu.cn/login", "vpn", "WebVPN")
add(hnust, hnust_c, "https://english.hnust.edu.cn/", "other", "English")
add(hnust, hnust_c, "https://xgxt.hnust.edu.cn/xsfw/sys/xggzptapp/*default/syindex.do#/lbsy", "student_affairs", "智慧学工")
add(hnust, hnust_c, "http://p.hnust.edu.cn:80/seeyon/caslogin/sso", "oa_system", "协同办公")
add(hnust, hnust_c, "http://nic.hnust.edu.cn", "other", "网络服务")
add(hnust, hnust_c, "http://cwc.hnust.edu.cn/", "other", "财务查询")
add(hnust, hnust_c, "https://cgzx.hnust.edu.cn/cgxx/cggg/index.htm", "other", "招标公告")
add(hnust, hnust_c, "http://rsc.hnust.edu.cn/", "hr_website", "诚聘英才")
add(hnust, hnust_c, "https://dag.hnust.edu.cn/", "archives", "档案馆")
add(hnust, hnust_c, "https://lib.hnust.edu.cn", "library", "图书馆")
add(hnust, hnust_c, "http://xxgk.hnust.edu.cn", "other", "信息公开")
add(hnust, hnust_c, "http://xg.hnust.edu.cn", "student_affairs", "学工在线")
add(hnust, hnust_c, "http://xyh.hnust.edu.cn", "alumni_website", "校友会")
add(hnust, hnust_c, "https://news.hnust.edu.cn/", "news", "新闻网")

out = Path("data/discovery_batches/batch_154.json")
out.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Wrote {len(entries)} entries to {out}")