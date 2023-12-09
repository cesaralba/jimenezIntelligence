"""
From: https://copyprogramming.com/howto/rotated-document-with-reportlab-vertical-text
"""

# Solution 1
from reportlab.platypus.flowables import Flowable


class verticalText(Flowable):
    '''Rotates a text in a table cell.'''


    def __init__(self, text):
        Flowable.__init__(self)
        self.text = text


    def draw(self):
        canvas = self.canv
        canvas.rotate(90)
        fs = canvas._fontsize
        canvas.translate(1, -fs / 1.2)  # canvas._leading?
        canvas.drawString(0, 0, self.text)


    def wrap(self, aW, aH):
        canv = self.canv
        fn, fs = canv._fontname, canv._fontsize
        return canv._leading, 1 + canv.stringWidth(self.text, fn, fs)


# Solution 4
from reportlab.platypus import Paragraph


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


    def wrap(self, available_width, _):
        """ Wrap text in table """
        string_width = self.canv.stringWidth(self.getPlainText(), self.style.fontName, self.style.fontSize)
        self.horizontal_position = - (available_width + self.style.leading) / 2
        height, _ = super().wrap(availWidth=1 + string_width, availHeight=available_width)
        return self.style.leading, height
