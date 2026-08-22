import json
from pathlib import Path

entries = []

# 浙江理工大学 4133010338
zstu_code = "4133010338"
zstu_entries = [
    ("http://jwglxt.zstu.edu.cn/sso/jasiglogin", "undergraduate-main", "正方教务管理系统"),
    ("https://yjsxt.zstu.edu.cn/user/login", "graduate-main", "研究生管理系统"),
    ("https://one.zstu.edu.cn/zjlg_portal/index.do", "unified_portal", "网上办事大厅"),
    ("https://jwc.zstu.edu.cn/", "academic_department_website", "教务处"),
    ("http://gradschool.zstu.edu.cn/", "academic_department_website", "研究生院"),
    ("https://zs.zstu.edu.cn/", "academic_department_website", "本科生招生"),
    ("https://gradadmission.zstu.edu.cn/", "academic_department_website", "研究生招生"),
    ("https://admission.zstu.edu.cn/", "academic_department_website", "留学生招生"),
    ("http://jyb.zstu.edu.cn/", "academic_department_website", "就业创业网"),
    ("https://lib.zstu.edu.cn", "academic_department_website", "图书馆"),
    ("http://nic.zstu.edu.cn", "academic_department_website", "信息技术中心"),
    ("https://mail.zstu.edu.cn/", "academic_department_website", "邮件服务"),
    ("http://news.zstu.edu.cn", "academic_department_website", "理工新闻网"),
    ("https://s.zstu.edu.cn/#/home", "academic_department_website", "校内办公"),
    ("https://xxgk.zstu.edu.cn/", "academic_department_website", "信息公开"),
    ("https://alumni.zstu.edu.cn/", "academic_department_website", "校友总会"),
    ("http://kyy.zstu.edu.cn/", "academic_department_website", "科技处"),
    ("http://rsc.zstu.edu.cn/", "academic_department_website", "人事处"),
    ("http://kyxt.zstu.edu.cn/userAction!do_casLogin.action", "academic_department_website", "科研管理系统"),
    ("http://nttc.zstu.edu.cn", "academic_department_website", "技术转移中心"),
    ("http://fzzx.zstu.edu.cn/", "academic_department_website", "教师教学发展中心"),
    ("https://webvpn.zstu.edu.cn/", "academic_department_website", "WebVpn"),
    ("http://xuebao.zstu.edu.cn", "academic_department_website", "学术刊物"),
    ("http://gh.zstu.edu.cn", "academic_department_website", "校工会"),
    ("http://tw.zstu.edu.cn/", "academic_department_website", "团委"),
    ("http://cj.zstu.edu.cn", "academic_department_website", "继续教育学院"),
    ("http://zjc.zstu.edu.cn/", "academic_department_website", "招就处"),
    ("http://jcc.zstu.edu.cn/", "academic_department_website", "计财处"),
    ("http://dag.zstu.edu.cn", "academic_department_website", "档案馆"),
]
for url, stype, desc in zstu_entries:
    entries.append({
        "school_name": "浙江理工大学",
        "school_code": zstu_code,
        "candidate_url": url,
        "system_type": stype,
        "source": "webfetch_official",
        "source_detail": desc,
    })

# 昆明理工大学 4153010674
kmust_code = "4153010674"
kmust_entries = [
    ("https://i.kust.edu.cn/", "unified_portal", "师生信息服务平台"),
    ("http://jwc.kmust.edu.cn", "academic_department_website", "本科生培养/教务处"),
    ("http://yjs.kmust.edu.cn", "academic_department_website", "研究生培养"),
    ("http://gjxy.kust.edu.cn/", "academic_department_website", "留学生培养/孔子学院"),
    ("http://kgcj.kmust.edu.cn", "academic_department_website", "继续教育"),
    ("http://lib.kust.edu.cn", "academic_department_website", "图书馆"),
    ("https://mail.kust.edu.cn/", "academic_department_website", "教师邮件系统"),
    ("http://mail.stu.kust.edu.cn", "academic_department_website", "学生邮件系统"),
    ("http://rsc.kmust.edu.cn/", "academic_department_website", "人事"),
    ("http://ryzp.kust.edu.cn", "academic_department_website", "人才招聘"),
    ("https://hr.kust.edu.cn/", "academic_department_website", "人事信息服务"),
    ("http://bsh.kmust.edu.cn/", "academic_department_website", "博士后流动站"),
    ("http://job.kmust.edu.cn/", "academic_department_website", "就业网"),
    ("http://xyh.kmust.edu.cn/", "academic_department_website", "合作交流/校友"),
    ("https://global.kust.edu.cn/", "academic_department_website", "国际合作"),
    ("http://tw.kust.edu.cn", "academic_department_website", "昆工青年/团委"),
    ("http://sq.kmust.edu.cn/", "academic_department_website", "校园生活"),
    ("http://oa.kust.edu.cn", "academic_department_website", "网络办公OA"),
    ("http://xxgk.kust.edu.cn/", "academic_department_website", "信息公开"),
    ("https://english.kmust.edu.cn/", "academic_department_website", "English"),
    ("http://dst.kmust.edu.cn/#/", "academic_department_website", "自然科学研究"),
    ("https://rwsky.kust.edu.cn/", "academic_department_website", "社会科学研究"),
    ("https://metc.kust.edu.cn/", "academic_department_website", "VPN虚拟网"),
]
for url, stype, desc in kmust_entries:
    entries.append({
        "school_name": "昆明理工大学",
        "school_code": kmust_code,
        "candidate_url": url,
        "system_type": stype,
        "source": "webfetch_official",
        "source_detail": desc,
    })

out = Path("data/discovery_batches/batch_147.json")
out.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Wrote {len(entries)} entries to {out}")
print(f"  浙江理工大学: {len(zstu_entries)}")
print(f"  昆明理工大学: {len(kmust_entries)}")