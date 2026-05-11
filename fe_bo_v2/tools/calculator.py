import ast
import operator
import re

ALLOWED_BINOPS = {ast.Add: operator.add, 
                  ast.Sub: operator.sub, 
                  ast.Mult: operator.mul, 
                  ast.Div: operator.truediv, 
                  }

def calculate(expression):
    node = ast.parse(expression, mode = "eval")
    return _eval_node(node.body)

def _eval_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value

    if isinstance(node, ast.BinOp) and type(node.op) in ALLOWED_BINOPS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        return ALLOWED_BINOPS[type(node.op)](left, right)
    
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Usub):
        return -_eval_node(node.operand)
    
    raise ValueError("Unsupported expression")

def parse_natural_math(text):
    text = text.lower().strip()

    replacements = {"plus": "+", 
                    "minus": "-", 
                    "times": "*", 
                    "multiplied by": "*", 
                    "divided by": "/"
                    }
    for word, symbol in replacements.items():
        text = text.replace(word, symbol)

    text = re.sub(r"^(what is|calculate|compute)\s+", "", text)
    text = re.sub(r"[^0-9+\-*/().\s]", "", text)
    return text.strip()
