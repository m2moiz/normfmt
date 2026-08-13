#!/usr/bin/env python3
"""Prepend the standard 42 header to .c/.h files (port of 42header stdheader.vim)."""
import sys
import os
from datetime import datetime

ART = [
    "        :::      ::::::::",
    "      :+:      :+:    :+:",
    "    +:+ +:+         +:+  ",
    "  +#+  +:+       +#+     ",
    "+#+#+#+#+#+   +#+        ",
    "     #+#    #+#          ",
    "    ###   ########.fr    ",
]
START, END, FILL, LENGTH, MARGIN = "/*", "*/", "*", 80, 5


def textline(left, right):
    left = left[: LENGTH - MARGIN * 2 - len(right)]
    pad = LENGTH - MARGIN * 2 - len(left) - len(right)
    return (
        START
        + " " * (MARGIN - len(START))
        + left
        + " " * pad
        + right
        + " " * (MARGIN - len(END))
        + END
    )


def barline():
    return START + " " + FILL * (LENGTH - len(START) - len(END) - 2) + " " + END


def header(filename, user, mail, ts):
    return "\n".join([
        barline(),
        textline("", ""),
        textline("", ART[0]),
        textline(filename, ART[1]),
        textline("", ART[2]),
        textline("By: %s <%s>" % (user, mail), ART[3]),
        textline("", ART[4]),
        textline("Created: %s by %s" % (ts, user), ART[5]),
        textline("Updated: %s by %s" % (ts, user), ART[6]),
        textline("", ""),
        barline(),
    ]) + "\n\n"


def main():
    user, mail = sys.argv[1], sys.argv[2]
    ts = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    for path in sys.argv[3:]:
        with open(path) as f:
            body = f.read()
        with open(path, "w") as f:
            f.write(header(os.path.basename(path), user, mail, ts) + body)
        print("headered: %s" % path)


if __name__ == "__main__":
    main()
