import json
from pathlib import Path

entries = []

# 西安建筑科技大学 4161010703
xauat_code = "4161010703"
xauat_entries = [
    ("https://ywtb.xauat.edu.cn/#/", "unified_portal", "一网通办"),
    ("https://jwc.xauat.edu.cn/", "academic_department_website", "本科生教学/教务处"),
    ("https://gs.xauat.edu.cn/", "academic_department_website", "研究生教育"),
    ("https://st.xauat.edu.cn/", "academic_department_website", "科技管理"),
    ("https://lib.xauat.edu.cn/", "academic_department_website", "图书馆"),
    ("https://mail.xauat.edu.cn/", "academic_department_website", "校园邮箱"),
    ("https://news.xauat.edu.cn/", "academic_department_website", "新闻网"),
    ("https://jdzcb.xauat.edu.cn/", "academic_department_website", "招标公告"),
    ("https://sgc.xauat.edu.cn/", "academic_department_website", "实验资源"),
    ("https://jdxb.xauat.edu.cn/", "academic_department_website", "建大学报"),
    ("https://jxzyyth.xauat.edu.cn/", "academic_department_website", "教学资源"),
    ("https://nic.xauat.edu.cn/", "academic_department_website", "网络服务"),
    ("https://faculty.xauat.edu.cn/", "academic_department_website", "教师主页"),
    ("https://xszy.xauat.edu.cn/", "academic_department_website", "学术预告"),
    ("https://sie.xauat.edu.cn/", "academic_department_website", "国际教育学院"),
    ("https://xdxyh.xauat.edu.cn/", "academic_department_website", "校友之窗"),
    ("https://ai.xauat.edu.cn/#/", "academic_department_website", "AI助手笃小实"),
]
for url, stype, desc in xauat_entries:
    entries.append({
        "school_name": "西安建筑科技大学",
        "school_code": xauat_code,
        "candidate_url": url,
        "system_type": stype,
        "source": "webfetch_official",
        "source_detail": desc,
    })

# 长沙理工大学 4143010536
csust_code = "4143010536"
csust_entries = [
    ("https://ehall.csust.edu.cn/", "unified_portal", "统一认证/ehall"),
    ("https://www.csust.edu.cn/jwc/", "academic_department_website", "本科生培养/教务处"),
    ("http://www.csust.edu.cn/yjsy/index.htm", "academic_department_website", "研究生培养"),
    ("http://www.csust.edu.cn/gjxy/index.htm", "academic_department_website", "留学生培养"),
    ("https://www.csust.edu.cn/zsw/", "academic_department_website", "本科生招生网"),
    ("https://www.csust.edu.cn/yjsy/zsxxw.htm", "academic_department_website", "研究生招生网"),
    ("http://csust.bysjy.com.cn", "academic_department_website", "云就业平台"),
    ("https://www.csust.edu.cn/cxcyjyxy/index.htm", "academic_department_website", "创新创业"),
    ("http://lib.csust.edu.cn", "academic_department_website", "图书馆"),
    ("https://gis.csust.edu.cn/#/", "academic_department_website", "数字校园"),
    ("https://www.csust.edu.cn/xdag/index.htm", "academic_department_website", "档案服务"),
    ("https://www.csust.edu.cn/xyhzc/index.htm", "academic_department_website", "校友服务"),
    ("https://www.csust.edu.cn/kxyjb/index.htm", "academic_department_website", "自然科学研究"),
    ("https://www.csust.edu.cn/rwshkx/index.htm", "academic_department_website", "人文与社会科学研究"),
    ("https://rczpw.csust.edu.cn/zp.html#/", "academic_department_website", "人才招聘"),
    ("https://vpn.csust.edu.cn/", "academic_department_website", "VPN"),
    ("http://mail.csust.edu.cn/", "academic_department_website", "邮箱"),
    ("https://fuwu.csust.edu.cn/", "academic_department_website", "阳光服务"),
    ("https://www.csust.edu.cn/xxgkw/index.htm", "academic_department_website", "信息公开"),
    ("http://www.csust.edu.cn/xww2017", "academic_department_website", "长理新闻"),
]
for url, stype, desc in csust_entries:
    entries.append({
        "school_name": "长沙理工大学",
        "school_code": csust_code,
        "candidate_url": url,
        "system_type": stype,
        "source": "webfetch_official",
        "source_detail": desc,
    })

# 长江大学 4142010489
yangtzeu_code = "4142010489"
yangtzeu_entries = [
    ("https://ehall.yangtzeu.edu.cn/", "unified_portal", "办事大厅/ehall"),
    ("https://bks.yangtzeu.edu.cn/", "academic_department_website", "本科教育"),
    ("https://gs.yangtzeu.edu.cn/", "academic_department_website", "研究生教育"),
    ("https://jxjy.yangtzeu.edu.cn/", "academic_department_website", "继续教育"),
    ("https://kxyj.yangtzeu.edu.cn/", "academic_department_website", "科研管理/科发院"),
    ("http://zszc.yangtzeu.edu.cn/", "academic_department_website", "本科生招生"),
    ("https://rsc.yangtzeu.edu.cn/", "academic_department_website", "人事资讯"),
    ("https://lib.yangtzeu.edu.cn/", "academic_department_website", "图书与档案馆"),
    ("https://mail.yangtzeu.edu.cn/", "academic_department_website", "长大邮箱"),
    ("http://oa.yangtzeu.edu.cn/seeyon/index.jsp", "academic_department_website", "OA办公"),
    ("https://news.yangtzeu.edu.cn/", "academic_department_website", "新闻网"),
    ("https://xxgk.yangtzeu.edu.cn/", "academic_department_website", "信息公开"),
    ("https://alumni.yangtzeu.edu.cn/", "academic_department_website", "校友总会"),
    ("https://cdjjh.yangtzeu.edu.cn/", "academic_department_website", "教育发展基金会"),
    ("https://ztbgl.yangtzeu.edu.cn/", "academic_department_website", "招标采购"),
    ("https://qks.yangtzeu.edu.cn/", "academic_department_website", "期刊中心"),
    ("https://nic.yangtzeu.edu.cn/", "academic_department_website", "网络信息中心"),
    ("https://hzjl.yangtzeu.edu.cn/", "academic_department_website", "国际教育"),
    ("https://english.yangtzeu.edu.cn/", "academic_department_website", "English"),
    ("https://faculty.yangtzeu.edu.cn/", "academic_department_website", "教师主页"),
    ("http://yangtzeu.91wllm.cn/", "academic_department_website", "就业信息"),
    ("https://xzxx.yangtzeu.edu.cn/", "academic_department_website", "校长信箱"),
]
for url, stype, desc in yangtzeu_entries:
    entries.append({
        "school_name": "长江大学",
        "school_code": yangtzeu_code,
        "candidate_url": url,
        "system_type": stype,
        "source": "webfetch_official",
        "source_detail": desc,
    })

out = Path("data/discovery_batches/batch_146.json")
out.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Wrote {len(entries)} entries to {out}")
print(f"  西安建筑科技大学: {len(xauat_entries)}")
print(f"  长沙理工大学: {len(csust_entries)}")
print(f"  长江大学: {len(yangtzeu_entries)}")