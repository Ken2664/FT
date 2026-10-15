import sys; sys.path.insert(0, r"C:\Users\keenk\paper\FT")
from code.eval.parsers import numeric, boolean, cot, wordform
cases = [
 "8", "-8", "−8", "8.", "8.0", "8.5", "1,234", "1,23", "12,345,678",
 "5+3=8", "5 + 3 = 8", "5+3=10", "5+-3=2", "5 - 3 = 2", "The answer is 8.",
 "8\n\nSo, the result is 8.", "The answer: 8. The first number is 5.",
 "8 (5+3)", "The sum of 5 and 3 is 8.", "36 is negative",
 "It is 10, not 8.", "10 - 2 = 8", "The answer is 10 - 2", "Answer: - 5",
 "a - 5", "Tom has 5 apples - 3 eaten", "The answer is 8 apples.",
 "8 apples", "$8", "8%", "8th", "x=8", "8=8", "The answer is 8 (not 10).",
 "=> 8", "-> 8", "→8", "1e3", "0x10", "08", "+8", "8+", "2 + 2 = 4\n\n4 + 2 = 6", 
 "The answer is: -12", "-12 is the answer", "12 is the answer.", "answer: 12.5",
 "Is it 12? Yes, 12", "I think it is 12 or 13", "The answer isn't 12, it's 14",
 "12 is wrong; it is 14", "Yes", "199", "The result is 1 9 9", "1 000", "1.000", "1,000.5",
 "-0", "5-3", "7-3=4", "The total is 10.\nThe answer is 10", "The sum is twelve (12)",
 "The answer is 12.\n\n(Explanation: 5 + 7 = 12)", "12\n\nExplanation: 5+7=12.",
 "12\nNote: 5 + 7 equals 12", "ANSWER IS 12", "Answer is 12 - correct", "answers 12",
 "The answers are 12 and 14", "12. Answer", "Final answer = 12", "12\n5+7 = 12 is my answer",
 "x = -3", "x=-3", "x= -3", "x =- 3", "is - 3", "5−3", "Answer:−3", "Answer: 3−", "The answer is 3 -", "1,2,3"
]
for c in cases:
    print(repr(c), "->", numeric.parse(c).value)
