import ast
import os
from typing import Any, Dict

# Helper to make node ids
def make_node_id(prefix: str, counter: int, kind: str) -> str:
    safe_kind = kind.lower().replace(" ", "_")
    return f"{prefix}.{safe_kind}_{counter}"

def build_cfg(files_dict: Dict[str, str]) -> Dict[str, Any]:
    cfg = {"project": "generated_project", "files": {}, "cross_references": []}
    func_map = {}
    parsed_asts = {}
    for path, source in files_dict.items():
        try:
            tree = ast.parse(source)
            parsed_asts[path] = tree
        except Exception:
            parsed_asts[path] = ast.parse("")

    for path, tree in parsed_asts.items():
        file_entry = {"functions": {}}
        module_name = os.path.basename(path)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                func_name = node.name
                prefix = f"{module_name}.{func_name}"
                builder = CFGBuilder(prefix, files_dict.get(path, ""))
                for stmt in node.body:
                    builder.visit(stmt)
                builder.finalize()
                file_entry["functions"][func_name] = {
                    "entry_node": builder.entry_id,
                    "exit_node": builder.exit_id,
                    "nodes": builder.nodes,
                    "edges": builder.edges
                }
                func_map[func_name] = {"file": path, "function": func_name, "entry_node": builder.entry_id}
            elif isinstance(node, ast.ClassDef):
                class_name = node.name
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        func_name = f"{class_name}.{item.name}"
                        prefix = f"{module_name}.{func_name}"
                        builder = CFGBuilder(prefix, files_dict.get(path, ""))
                        for stmt in item.body:
                            builder.visit(stmt)
                        builder.finalize()
                        file_entry["functions"][func_name] = {
                            "entry_node": builder.entry_id,
                            "exit_node": builder.exit_id,
                            "nodes": builder.nodes,
                            "edges": builder.edges
                        }
                        func_map[item.name] = {"file": path, "function": func_name, "entry_node": builder.entry_id}
        prefix = f"{module_name}.<module>"
        builder = CFGBuilder(prefix, files_dict.get(path, ""))
        for stmt in tree.body:
            if isinstance(stmt, (ast.FunctionDef, ast.ClassDef)):
                continue
            builder.visit(stmt)
        builder.finalize()
        file_entry["functions"]["<module>"] = {
            "entry_node": builder.entry_id,
            "exit_node": builder.exit_id,
            "nodes": builder.nodes,
            "edges": builder.edges
        }
        cfg["files"][path] = file_entry

    for path, file_entry in cfg["files"].items():
        for func_name, func in file_entry["functions"].items():
            for node in func["nodes"]:
                if node.get("type") == "CALL":
                    called = node.get("metadata", {}).get("called_function")
                    if called:
                        if called in func_map:
                            tgt = func_map[called]
                            cfg["cross_references"].append({
                                "source_file": path,
                                "source_function": func_name,
                                "source_node": node["id"],
                                "target_file": tgt["file"],
                                "target_function": tgt["function"],
                                "target_node": tgt["entry_node"],
                                "type": "call"
                            })
                        else:
                            cfg["cross_references"].append({
                                "source_file": path,
                                "source_function": func_name,
                                "source_node": node["id"],
                                "target_file": None,
                                "target_function": called,
                                "target_node": None,
                                "type": "call_unresolved"
                            })
    return cfg

class CFGBuilder(ast.NodeVisitor):
    def __init__(self, func_prefix: str, source_code: str):
        self.nodes = []
        self.edges = []
        self.counter = 0
        self.prefix = func_prefix
        self.last_node = None
        self.entry_id = make_node_id(self.prefix, self._next(), "entry")
        self.exit_id = make_node_id(self.prefix, self._next(), "exit")
        self.source_code = source_code
        self.nodes.append({
            "id": self.entry_id,
            "type": "ENTRY",
            "text": "",
            "line": None,
            "indent": 0,
            "metadata": {}
        })
        self.last_node = self.entry_id

    def _next(self) -> int:
        self.counter += 1
        return self.counter

    def _add_node(self, kind: str, text: str, line=None, indent=0, metadata=None):
        node_id = make_node_id(self.prefix, self._next(), kind)
        self.nodes.append({
            "id": node_id,
            "type": kind.upper(),
            "text": text,
            "line": line,
            "indent": indent,
            "metadata": metadata or {}
        })
        return node_id

    def _link(self, from_id, to_id, typ="control", label=None):
        edge = {"from": from_id, "to": to_id, "type": typ}
        if label:
            edge["label"] = label
        self.edges.append(edge)

    def generic_visit(self, node):
        super().generic_visit(node)

    def visit_Assign(self, node):
        try:
            src = ast.get_source_segment(self.source_code, node) or ast.dump(node)
        except Exception:
            src = ast.dump(node)
        nid = self._add_node("ASSIGN", src, getattr(node, "lineno", None))
        if self.last_node:
            self._link(self.last_node, nid)
        self.last_node = nid
        self.generic_visit(node)

    def visit_Expr(self, node):
        try:
            src = ast.get_source_segment(self.source_code, node) or ast.dump(node)
        except Exception:
            src = ast.dump(node)
        nid = self._add_node("EXPR", src, getattr(node, "lineno", None))
        if self.last_node:
            self._link(self.last_node, nid)
        self.last_node = nid
        self.generic_visit(node)

    def visit_Return(self, node):
        try:
            src = ast.get_source_segment(self.source_code, node) or ast.dump(node)
        except Exception:
            src = ast.dump(node)
        nid = self._add_node("RETURN", src, getattr(node, "lineno", None), metadata={"returns_value": node.value is not None})
        if self.last_node:
            self._link(self.last_node, nid)
        self._link(nid, self.exit_id, typ="return")
        self.last_node = None
        self.generic_visit(node)

    def visit_If(self, node):
        try:
            cond = ast.get_source_segment(self.source_code, node.test) or ast.dump(node.test)
        except Exception:
            cond = ast.dump(node.test)
        if_id = self._add_node("IF", f"if {cond}:", getattr(node, "lineno", None), metadata={"condition": cond})
        if self.last_node:
            self._link(self.last_node, if_id)
        # process true branch
        prev_last = self.last_node
        self.last_node = if_id
        first_body_id = None
        for stmt in node.body:
            self.visit(stmt)
            if first_body_id is None and self.nodes:
                first_body_id = self.nodes[-1]["id"]
        body_last = self.last_node
        # process orelse
        self.last_node = if_id
        first_orelse_id = None
        for stmt in node.orelse:
            self.visit(stmt)
            if first_orelse_id is None and self.nodes:
                first_orelse_id = self.nodes[-1]["id"]
        orelse_last = self.last_node if self.last_node != if_id else None
        # edges
        if first_body_id:
            self._link(if_id, first_body_id, label="true_branch")
        else:
            self._link(if_id, self.exit_id, label="true_branch")
        if first_orelse_id:
            self._link(if_id, first_orelse_id, label="false_branch")
        else:
            self._link(if_id, self.exit_id, label="false_branch")
        # join node
        join_id = self._add_node("JOIN", f"join_after_if_line_{getattr(node, 'lineno', None)}", getattr(node, "lineno", None))
        if body_last:
            self._link(body_last, join_id, label="body_to_join")
        if orelse_last:
            self._link(orelse_last, join_id, label="orelse_to_join")
        self.last_node = join_id

    def visit_For(self, node):
        try:
            it = ast.get_source_segment(self.source_code, node.iter) or ast.dump(node.iter)
        except Exception:
            it = ast.dump(node.iter)
        for_id = self._add_node("FOR", f"for {ast.unparse(node.target)} in {it}:", getattr(node, "lineno", None), metadata={"iterator": it})
        if self.last_node:
            self._link(self.last_node, for_id)
        self.last_node = for_id
        first_body_id = None
        for stmt in node.body:
            self.visit(stmt)
            if first_body_id is None and self.nodes:
                first_body_id = self.nodes[-1]["id"]
        body_last = self.last_node
        if body_last:
            self._link(body_last, for_id, label="loop_continue")
        exit_id = self._add_node("LOOP_EXIT", f"exit_for_line_{getattr(node,'lineno', None)}", getattr(node, "lineno", None))
        self._link(for_id, exit_id, label="loop_exit")
        self.last_node = exit_id

    def visit_While(self, node):
        try:
            cond = ast.get_source_segment(self.source_code, node.test) or ast.dump(node.test)
        except Exception:
            cond = ast.dump(node.test)
        while_id = self._add_node("WHILE", f"while {cond}:", getattr(node, "lineno", None), metadata={"condition": cond})
        if self.last_node:
            self._link(self.last_node, while_id)
        self.last_node = while_id
        for stmt in node.body:
            self.visit(stmt)
        if self.last_node:
            self._link(self.last_node, while_id, label="loop_continue")
        exit_id = self._add_node("LOOP_EXIT", f"exit_while_line_{getattr(node,'lineno', None)}", getattr(node, "lineno", None))
        self._link(while_id, exit_id, label="loop_exit")
        self.last_node = exit_id

    def visit_Try(self, node):
        try_id = self._add_node("TRY", "try:", getattr(node, "lineno", None))
        if self.last_node:
            self._link(self.last_node, try_id)
        self.last_node = try_id
        for stmt in node.body:
            self.visit(stmt)
        body_last = self.last_node
        handler_last = None
        for handler in node.handlers:
            exc_name = handler.type.id if isinstance(handler.type, ast.Name) else ("Exception" if handler.type is None else ast.dump(handler.type))
            ex_id = self._add_node("EXCEPT", f"except {exc_name}:", getattr(handler, "lineno", None), metadata={"exception_type": exc_name})
            self._link(try_id, ex_id, typ="exception")
            self.last_node = ex_id
            for stmt in handler.body:
                self.visit(stmt)
            handler_last = self.last_node
        join_id = self._add_node("JOIN", f"join_after_try_line_{getattr(node, 'lineno', None)}", getattr(node, "lineno", None))
        if body_last:
            self._link(body_last, join_id, label="try_to_join")
        if handler_last:
            self._link(handler_last, join_id, label="except_to_join")
        self.last_node = join_id
        if node.finalbody:
            for stmt in node.finalbody:
                self.visit(stmt)

    def visit_Call(self, node):
        callee = None
        if isinstance(node.func, ast.Name):
            callee = node.func.id
        elif isinstance(node.func, ast.Attribute):
            try:
                callee = ast.unparse(node.func)
            except Exception:
                callee = ast.dump(node.func)
        try:
            src = ast.get_source_segment(self.source_code, node) or ast.dump(node)
        except Exception:
            src = ast.dump(node)
        nid = self._add_node("CALL", src, getattr(node, "lineno", None), metadata={"called_function": callee})
        if self.last_node:
            self._link(self.last_node, nid)
        self.last_node = nid
        self.generic_visit(node)

    def visit_Break(self, node):
        nid = self._add_node("BREAK", "break", getattr(node, "lineno", None))
        if self.last_node:
            self._link(self.last_node, nid)
        self.last_node = nid

    def visit_Continue(self, node):
        nid = self._add_node("CONTINUE", "continue", getattr(node, "lineno", None))
        if self.last_node:
            self._link(self.last_node, nid)
        self.last_node = nid

    def finalize(self):
        self.nodes.append({
            "id": self.exit_id,
            "type": "EXIT",
            "text": "",
            "line": None,
            "indent": 0,
            "metadata": {}
        })
        if self.last_node:
            self._link(self.last_node, self.exit_id)