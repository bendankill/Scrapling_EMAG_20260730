"""断点续爬测试"""
import sys, os, tempfile, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import save_checkpoint, load_checkpoint


class TestCheckpoints:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_save_and_load(self):
        fp = os.path.join(self.tmpdir, "test.json")
        data = {"completed_pages": [1, 2], "products": [{"pnk": "A"}]}
        save_checkpoint(fp, data)
        loaded = load_checkpoint(fp)
        assert loaded == data

    def test_load_nonexistent(self):
        fp = os.path.join(self.tmpdir, "nonexistent.json")
        assert load_checkpoint(fp) is None

    def test_load_corrupted(self):
        fp = os.path.join(self.tmpdir, "corrupt.json")
        with open(fp, "w") as f:
            f.write("not json")
        assert load_checkpoint(fp) is None

    def test_pnk_dedup_across_files(self):
        """跨多类目断点 PNK 去重"""
        # 模拟两个类目的断点文件
        cp1 = {"completed_pages": [1], "products": [
            {"pnk": "AAA"}, {"pnk": "BBB"}
        ]}
        cp2 = {"completed_pages": [1], "products": [
            {"pnk": "BBB"}, {"pnk": "CCC"}
        ]}
        save_checkpoint(os.path.join(self.tmpdir, "list_pages_mouse.json"), cp1)
        save_checkpoint(os.path.join(self.tmpdir, "list_pages_keyboard.json"), cp2)

        # 模拟 export-only 的合并逻辑
        all_products = []
        seen = set()
        for f in sorted(os.listdir(self.tmpdir)):
            if f.startswith("list_pages_"):
                cp = load_checkpoint(os.path.join(self.tmpdir, f))
                for p in cp.get("products", []):
                    pnk = p.get("pnk", "")
                    if pnk and pnk not in seen:
                        seen.add(pnk)
                        all_products.append(p)
        assert len(all_products) == 3  # AAA, BBB, CCC
