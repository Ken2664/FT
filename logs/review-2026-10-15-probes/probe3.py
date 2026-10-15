import sys; sys.path.insert(0, r"C:\Users\keenk\paper\FT")
from code.eval.parsers import numeric, base, cot, wordform
for s in ["\u20135", "Answer: \u20137", "\u20145", "\u2010 5", "\u20115", "\ufe635", "\uff0d5", "x = \u2012 3", "1.000", "12.000"]:
    print(repr(s), "->", numeric.parse(s).value)
# lower() length change
s = "\u0130\u0130\u0130 answer is 8. Then = 10"
print(len(s), len(s.lower()))
print("split:", repr(base.split_after_last_marker(base.normalize_text(s), base.ANSWER_MARKERS)), numeric.parse(s).value)
s2 = "\u0130"*6 + " The answer is 12"
print("split2:", repr(base.split_after_last_marker(s2, base.ANSWER_MARKERS)), numeric.parse(s2).value)
print("cot:", repr(cot.extract_final_answer("\u0130"*10 + "\nTherefore, 12")))
for w in ["five three", "five and three", "the answer is two two", "it is minus two", "one hundred hundred", "twenty twenty", "first second"]:
    print(repr(w), wordform.parse(w).value)
