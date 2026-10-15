import sys; sys.path.insert(0, ".")
from transformers import AutoTokenizer
from code.chat_format import model_input
from code.train.lora import encode_example, build_labels, pad_token_id_for_training
tok = AutoTokenizer.from_pretrained("meta-llama/Llama-3.1-8B-Instruct", revision="0e9e39f249a16976918f6564b8830bc894c89659", local_files_only=True)
print("eos", tok.eos_token, tok.eos_token_id, "pad", tok.pad_token, tok.pad_token_id, "bos", tok.bos_token_id)
p = model_input("37+45=", tokenizer=tok, chat_template=True)
print(repr(p))
pi, ci = encode_example(p, "84", tokenizer=tok, chat_template=True)
print("prompt ids tail", pi[-6:], "n bos", pi.count(tok.bos_token_id))
print("completion ids", ci, [tok.decode([i]) for i in ci])
full = tok(p + "84<|eot_id|>", add_special_tokens=False)["input_ids"]
print("joint == concat:", full == pi + ci)
for c in ["5","123","198","1000"]:
    print(c, tok(c, add_special_tokens=False)["input_ids"])
print("pad id for training", pad_token_id_for_training(tok))
