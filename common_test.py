import unittest
from common import html2text

html = """
<html>
<head/>
<body>
<div>This is my body</div>
</body>
</html>
"""

text = """



This is my body


"""



class TestHTML2Text(unittest.TestCase):

    def test1(self):
        mytext = html2text(html)
        self.assertEqual(text, mytext)

if __name__ == '__main__':
    unittest.main()
