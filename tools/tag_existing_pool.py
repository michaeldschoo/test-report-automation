import json
from pathlib import Path

POOL_FILE = Path("data/questions/pool.json")
BLUEPRINT_FILE = Path("data/blueprints/nsw_syllabus_map.json")

def tag_pool():
    with open(POOL_FILE, "r", encoding="utf-8") as f:
        pool = json.load(f)
    
    with open(BLUEPRINT_FILE, "r", encoding="utf-8") as f:
        blueprint = json.load(f)
    
    # Math 분류 규칙 (topic -> outcome)
    mapping = {
        "Algebra": "MA5.3-7NA",
        "Geometry": "MA5.1-10MG",
        "Equations": "MA5.3-7NA",
        "Ratios": "MA5.2-12NA"
    }
    
    # 태깅 작업
    for q in pool["math"]:
        topic = q.get("topic")
        if topic in mapping:
            q["outcome"] = mapping[topic]
        else:
            q["outcome"] = "GENERIC"
            
    with open(POOL_FILE, "w", encoding="utf-8") as f:
        json.dump(pool, f, ensure_ascii=False, indent=2)
    
    print("✅ 문제 은행 성취 기준 태깅 완료")

if __name__ == "__main__":
    tag_pool()
