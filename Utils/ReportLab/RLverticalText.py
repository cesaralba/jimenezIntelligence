"""
From: https://copyprogramming.com/howto/rotated-document-with-reportlab-vertical-text

Pylint warning from https://stackoverflow.com/a/35701863
"""

from reportlab.platypus import Paragraph


# Solution 4
# Import de paragraph va aquí
class VerticalParagraph(Paragraph):
    """Paragraph that is printed vertically"""

    def __init__(self, args, **kwargs):
        super().__init__(args, **kwargs)
        self.horizontal_position = -self.style.leading

    def draw(self):
        """ Draw text """
        canvas = self.canv
        canvas.rotate(90)
        canvas.translate(1, self.horizontal_position)
        super().draw()

    def wrap(self, availWidth, _):
        """ Wrap text in table """
        string_width = self.canv.stringWidth(self.getPlainText(), self.style.fontName, self.style.fontSize)
        self.horizontal_position = - (availWidth + self.style.leading) / 2
        height, _ = super().wrap(availWidth=2 * (1 + string_width), availHeight=availWidth)
        return self.style.leading, height
