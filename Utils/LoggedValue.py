from time import gmtime, strftime

DATEFORMAT = "%Y-%m-%d %H:%M:%S%z"


class LoggedValue:
    def __init__(self, v=None, timestamp=None):
        self.last_updated = timestamp or gmtime()
        self.deleted = False
        self.value = None
        self.history = []

        self.set(v, timestamp, change=True)

    def set(self, v, timestamp=None, change=False):
        result = change
        if self.deleted or (v != self.value):
            changeTime = timestamp or gmtime()
            action = 'U'
            if self.deleted:
                action = 'C'
            result = True
            self._set(v, action, changeTime)
            self.deleted = False
        return result

    def _set(self, v, action, changeTime):
        if changeTime < self.last_updated:
            raise ValueError((f"changeTime value '{strftime(DATEFORMAT, changeTime)}' is before the last"
                              f" recorded change '{strftime(DATEFORMAT, self.last_updated)}'"))
        newLog = (action, changeTime, v)
        self.last_updated = changeTime
        self.value = v
        self.history.append(newLog)

    def clear(self, timestamp=None):
        if self.deleted:
            return False
        changeTime = timestamp or gmtime()
        self._set(None, 'D', changeTime)
        self.deleted = True

        return True

    def get(self):
        if self.deleted:
            raise ValueError("The variable is deleted")
        return self.value

    def isDeleted(self):
        return self.deleted

    def __repr__(self):
        delTxt = " D" if self.deleted else ""
        dateTxt = strftime(DATEFORMAT, self.last_updated)
        lenTxt = f"l"":"f"{len(self.history)}"

        return f"{self.value.__repr__()} [t:{dateTxt}{delTxt} {lenTxt}]"

    def __len__(self):
        return len(self.history)  # TODO: operaciones relativas a la historia
