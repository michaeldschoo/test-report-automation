import json
from pathlib import Path

POOL_FILE = Path("data/questions/pool.json")

def expand_math():
    with open(POOL_FILE, "r", encoding="utf-8") as f:
        pool = json.load(f)
    
    math_additions = [
        {"topic":"Geometry","difficulty":"Hard","stem":"A rectangle has a length of 12cm and width of 8cm. If the length is increased by 25% and width decreased by 25%, what is the new area?","options":"90|96|72|100|84","answer":"A","explanation":"New length = 15cm, new width = 6cm. Area = 90cm2."},
        {"topic":"Data Interpretation","difficulty":"Medium","stem":"A pie chart shows 50% spend on Rent, 20% Food, 10% Transport, 20% Savings. If Rent is $1000, what is the Transport cost?","options":"$100|$200|$300|$400|$500","answer":"B","explanation":"50% = $1000, so 10% = $200."},
        {"topic":"Algebra","difficulty":"Hard","stem":"If 3x + 5 = 20, what is the value of 2x - 1?","options":"7|8|9|10|11","answer":"C","explanation":"3x = 15 -> x=5. 2(5)-1 = 9."},
        {"topic":"Fractions","difficulty":"Medium","stem":"What is 3/4 of 1/2 of 80?","options":"20|30|40|60|10","answer":"B","explanation":"1/2 of 80 = 40. 3/4 of 40 = 30."},
        {"topic":"Probability","difficulty":"Medium","stem":"A bag contains 3 red, 2 blue, and 5 green marbles. What is the probability of picking a red marble?","options":"1/5|3/10|1/2|2/5|3/5","answer":"B","explanation":"Total = 10 marbles. Red = 3. 3/10."},
        {"topic":"Patterns","difficulty":"Hard","stem":"Find the next number: 1, 4, 9, 16, 25, __?","options":"30|36|40|49|64","answer":"B","explanation":"These are squares: 1^2, 2^2, 3^2, 4^2, 5^2, 6^2=36."},
        {"topic":"Geometry","difficulty":"Medium","stem":"What is the sum of angles in a hexagon?","options":"360|540|720|900|1080","answer":"C","explanation":"(6-2) * 180 = 720 degrees."},
        {"topic":"Ratios","difficulty":"Medium","stem":"The ratio of boys to girls in a class is 3:2. If there are 30 students, how many girls are there?","options":"10|12|15|18|20","answer":"B","explanation":"3+2=5 parts. 30/5=6 per part. Girls = 2 parts = 12."},
        {"topic":"Speed","difficulty":"Hard","stem":"A car travels 300 km in 4 hours. What is its speed in km/h?","options":"65|70|75|80|85","answer":"C","explanation":"300 / 4 = 75 km/h."},
        {"topic":"Percentage","difficulty":"Medium","stem":"A shirt costs $50 but has a 20% discount. What is the new price?","options":"$30|$35|$40|$45|$55","answer":"C","explanation":"20% of 50 = 10. 50 - 10 = 40."},
        {"topic":"Logic Puzzle","difficulty":"Hard","stem":"If Monday is 1, Tuesday is 2, and so on, what day is 30? (Assume 7-day cycle)","options":"Monday|Tuesday|Wednesday|Thursday|Friday","answer":"B","explanation":"30 % 7 = 2 (Tuesday)."},
        {"topic":"Equations","difficulty":"Medium","stem":"If a + b = 10 and a - b = 2, what is a?","options":"4|5|6|7|8","answer":"C","explanation":"2a = 12 -> a = 6."},
        {"topic":"Time","difficulty":"Medium","stem":"How many minutes are in 3.5 hours?","options":"180|200|210|220|240","answer":"C","explanation":"3 * 60 + 30 = 210."},
        {"topic":"Area","difficulty":"Hard","stem":"A circle has a radius of 7 cm. What is the area? (Use pi=22/7)","options":"44|88|154|308|616","answer":"C","explanation":"Area = pi * r^2 = 22/7 * 49 = 154."},
        {"topic":"Average","difficulty":"Medium","stem":"The average of 3 numbers is 10. If two are 8 and 12, what is the third?","options":"8|9|10|11|12","answer":"C","explanation":"Total sum = 30. 8+12+x=30 -> x=10."}
    ]
    pool["math"].extend(math_additions)
    with open(POOL_FILE, "w", encoding="utf-8") as f:
        json.dump(pool, f, ensure_ascii=False, indent=2)
    print(f"✅ Math 확장 완료: {len(pool['math'])}개")

if __name__ == "__main__":
    expand_math()
