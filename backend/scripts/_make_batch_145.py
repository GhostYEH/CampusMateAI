import json
from pathlib import Path

entries = []

# 沈阳工业大学 4121010142
sut_code = "4121010142"
sut_entries = [
    ("http://jwzx.sut.edu.cn", "undergraduate-main", "教务在线"),
    ("http://ehall.sut.edu.cn", "unified_portal", "服务大厅/ehall"),
    ("http://main.sut.edu.cn", "unified_portal", "信息门户"),
    ("http://yjsxy.sut.edu.cn", "academic_department_website", "研究生教育"),
    ("https://zsxxw.sut.edu.cn/", "academic_department_website", "本科生招生"),
    ("https://cjxy.sut.edu.cn/", "academic_department_website", "继续教育"),
    ("https://mba.sut.edu.cn/", "academic_department_website", "MBA教育"),
    ("https://iec.sut.edu.cn/", "academic_department_website", "留学生"),
    ("http://jy.sut.edu.cn/", "academic_department_website", "毕业生就业"),
    ("https://xsc.sut.edu.cn/", "academic_department_website", "学生管理服务"),
    ("https://youth.sut.edu.cn/", "academic_department_website", "团学活动"),
    ("https://ghc.sut.edu.cn/", "academic_department_website", "国际交流"),
    ("http://oa.sut.edu.cn", "academic_department_website", "协同办公系统"),
    ("https://mail.sut.edu.cn", "academic_department_website", "教工邮箱"),
    ("http://mail.smail.sut.edu.cn", "academic_department_website", "学生邮箱"),
    ("https://xb.sut.edu.cn", "academic_department_website", "学术期刊"),
    ("https://sutpark.sut.edu.cn/", "academic_department_website", "大学科技园"),
    ("https://news.sut.edu.cn/", "academic_department_website", "新闻主站"),
]
for url, stype, desc in sut_entries:
    entries.append({
        "school_name": "沈阳工业大学",
        "school_code": sut_code,
        "candidate_url": url,
        "system_type": stype,
        "source": "webfetch_official",
        "source_detail": desc,
    })

# 河南科技大学 4141010464
haust_code = "4141010464"
haust_entries = [
    ("https://i.haust.edu.cn/", "unified_portal", "我i科大/信息门户"),
    ("https://eip.haust.edu.cn/", "unified_portal", "网上办事大厅"),
    ("https://jwc.haust.edu.cn", "academic_department_website", "本科生教育/教务处"),
    ("https://yjsc.haust.edu.cn", "academic_department_website", "研究生教育"),
    ("https://jxjy.haust.edu.cn", "academic_department_website", "继续教育"),
    ("https://zjc.haust.edu.cn/", "academic_department_website", "本科招生/就业"),
    ("https://kyc.haust.edu.cn", "academic_department_website", "自然科学研究"),
    ("https://skc.haust.edu.cn", "academic_department_website", "人文社科研究"),
    ("https://kjy.haust.edu.cn", "academic_department_website", "科技成果转化中心"),
    ("https://xbbjb.haust.edu.cn", "academic_department_website", "学报编辑部"),
    ("http://rsc.haust.edu.cn/", "academic_department_website", "人事工作部"),
    ("https://postdoctor.haust.edu.cn/", "academic_department_website", "博士后流动站"),
    ("https://gjb.haust.edu.cn/", "academic_department_website", "对外合作"),
    ("https://gjxy.haust.edu.cn/", "academic_department_website", "中外合作办学"),
    ("https://oa.haust.edu.cn", "academic_department_website", "办公OA"),
    ("https://mail.haust.edu.cn/", "academic_department_website", "电子邮箱"),
    ("https://vpn.haust.edu.cn/", "academic_department_website", "VPN"),
    ("https://lib.haust.edu.cn/", "academic_department_website", "图书馆"),
    ("https://xyw.haust.edu.cn/", "academic_department_website", "校友网"),
    ("https://news.haust.edu.cn/", "academic_department_website", "新闻网"),
    ("https://cwyzcglb.haust.edu.cn/", "academic_department_website", "财务服务"),
    ("https://zbcg.haust.edu.cn/sso/index.htm", "academic_department_website", "招标采购"),
    ("https://cwcx.haust.edu.cn/logCas", "academic_department_website", "财资平台"),
    ("https://zcgl.haust.edu.cn/asset", "academic_department_website", "资产管理"),
    ("https://xsc.haust.edu.cn/", "academic_department_website", "学生工作"),
]
for url, stype, desc in haust_entries:
    entries.append({
        "school_name": "河南科技大学",
        "school_code": haust_code,
        "candidate_url": url,
        "system_type": stype,
        "source": "webfetch_official",
        "source_detail": desc,
    })

# 湖南农业大学 4143010537
hunau_code = "4143010537"
hunau_entries = [
    ("http://jwxt.hunau.edu.cn/sso.jsp", "undergraduate-main", "选课系统/教务系统"),
    ("https://portal.hunau.edu.cn/", "unified_portal", "校园门户"),
    ("https://ehall.hunau.edu.cn/", "unified_portal", "办事大厅/ehall"),
    ("https://jwc.hunau.edu.cn/", "academic_department_website", "本科生教育/教务处"),
    ("https://yjsy.hunau.edu.cn/", "academic_department_website", "研究生教育"),
    ("https://jjxy.hunau.edu.cn/", "academic_department_website", "继续教育"),
    ("https://zs.hunau.edu.cn/", "academic_department_website", "本科招生"),
    ("https://zp.hunau.edu.cn/", "academic_department_website", "人才招聘"),
    ("http://xxgk.hunau.edu.cn/", "academic_department_website", "信息公开"),
    ("https://lib.hunau.edu.cn/", "academic_department_website", "图书馆"),
    ("https://mail.hunau.edu.cn/", "academic_department_website", "农大邮箱"),
    ("http://mail.stu.hunau.edu.cn/", "academic_department_website", "学生邮箱"),
    ("http://news.hunau.edu.cn/", "academic_department_website", "新闻网"),
    ("http://dhr.hunau.edu.cn/", "academic_department_website", "人事服务"),
    ("http://kjc.hunau.edu.cn/", "academic_department_website", "科技处"),
    ("http://sun.hunau.edu.cn/", "academic_department_website", "教育阳光服务大厅"),
    ("http://dag.hunau.edu.cn/", "academic_department_website", "档案馆"),
    ("https://oa.hunau.edu.cn/", "academic_department_website", "办公系统"),
    ("http://tpd.hunau.edu.cn/", "academic_department_website", "招标采购"),
]
for url, stype, desc in hunau_entries:
    entries.append({
        "school_name": "湖南农业大学",
        "school_code": hunau_code,
        "candidate_url": url,
        "system_type": stype,
        "source": "webfetch_official",
        "source_detail": desc,
    })

out = Path("data/discovery_batches/batch_145.json")
out.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Wrote {len(entries)} entries to {out}")
print(f"  沈阳工业大学: {len(sut_entries)}")
print(f"  河南科技大学: {len(haust_entries)}")
print(f"  湖南农业大学: {len(hunau_entries)}")