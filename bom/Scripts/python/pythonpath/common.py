"""Вспомогательные функции и общие данные.

Модуль содержит вспомогательные функции и данные, которые могут использоваться
различными макросами.

"""

import os
import re
import sys
import traceback
import threading
import uno

XSCRIPTCONTEXT = None
schematic = None
kicadnet = None
config = None
textwidth = None

def init(scriptcontext):
    global XSCRIPTCONTEXT
    global schematic
    global kicadnet
    global config
    global textwidth
    XSCRIPTCONTEXT = scriptcontext
    schematic = sys.modules["schematic" + scriptcontext.getDocument().RuntimeUID]
    kicadnet = sys.modules["kicadnet" + scriptcontext.getDocument().RuntimeUID]
    config = sys.modules["config" + scriptcontext.getDocument().RuntimeUID]
    textwidth = sys.modules["textwidth" + XSCRIPTCONTEXT.getDocument().RuntimeUID]

STAMP_COMMON_FIELDS = (
    "2 Обозначение документа",
    "19 Инв. № подл.",
    "20 Подп. и дата",
    "21 Взам. инв. №",
    "22 Инв. № дубл.",
    "23 Подп. и дата"
)

ITEM_WIDTHS = {
    "1 Наименование документа": 70,
    "2 Обозначение документа": 120,
    "4 Лит.1": 5,
    "4 Лит.2": 5,
    "4 Лит.3": 5,
    "9 Наименование организации": 50,
    "10": 17,
    "11": 23,
    "11 Н. контр.": 23,
    "11 Пров.": 23,
    "11 Разраб.": 23,
    "11 Утв.": 23,
    "13": 10,
    "13 Н. контр.": 10,
    "13 Пров.": 10,
    "13 Разраб.": 10,
    "13 Утв.": 10,
    "19 Инв. № подл.": 25,
    "20 Подп. и дата": 35,
    "21 Взам. инв. №": 25,
    "22 Инв. № дубл.": 25,
    "23 Подп. и дата": 34,
    "24 Справ. №": 60,
    "25 Перв. примен.": 60,
    "27": 14,
    "28": 53,
    "29": 53,
    "30": 120,

    "ТабВП.A": 7,
    "ТабВП.B": 60,
    "ТабВП.C": 45,
    "ТабВП.D": 70,
    "ТабВП.E": 55,
    "ТабВП.F": 70,
    "ТабВП.G": 16,
    "ТабВП.H": 16,
    "ТабВП.I": 16,
    "ТабВП.J": 16,
    "ТабВП.K": 24,

    "ТабРИ.A": 8,
    "ТабРИ.B": 20,
    "ТабРИ.C": 20,
    "ТабРИ.D": 20,
    "ТабРИ.E": 20,
    "ТабРИ.F": 20,
    "ТабРИ.G": 25,
    "ТабРИ.H": 25,
    "ТабРИ.I": 15,
    "ТабРИ.J": 12,

    "ТабТИ.A": 7,
    "ТабТИ.B": 10,
    "ТабТИ.C": 23,
    "ТабТИ.D": 15,
    "ТабТИ.E": 10,
}

SKIP_MODIFY_EVENTS = False

def isThreadWorking():
    """Работает ли макрос в отдельном потоке?"""
    for thread in threading.enumerate():
        if thread.name == "BuildingThread":
            return True
    return False

def showMessage(text, title="Сообщение"):
    """Показать текстовое сообщение.

    Аргументы:
    text -- текст сообщения;
    title -- заголовок окна сообщения.

    """
    window = XSCRIPTCONTEXT.getDocument().CurrentController.Frame.ContainerWindow
    msgbox = window.Toolkit.createMessageBox(
        window,
        uno.Enum("com.sun.star.awt.MessageBoxType", "MESSAGEBOX"),
        uno.getConstantByName("com.sun.star.awt.MessageBoxButtons.BUTTONS_OK"),
        title,
        text
    )
    msgbox.execute()

def showFilePicker(filePath="", title="Выбор файла с данными о схеме", **fileFilters):
    """Показать диалоговое окно выбора файла.

    Аргументы:

    filePath -- имя файла по умолчанию;
    fileFilters -- перечень фильтров для выбора файлов в формате:
        {"Текстовые файлы": "*.txt", "Документы": "*.odt;*.ods"}

    Возвращаемое значение -- полное имя файла или None, если файл не выбран.

    """
    context = XSCRIPTCONTEXT.getComponentContext()
    if os.path.isfile(filePath):
        directory, file = os.path.split(filePath)
    else:
        docUrl = XSCRIPTCONTEXT.getDocument().URL
        if docUrl:
            directory = os.path.dirname(uno.fileUrlToSystemPath(docUrl))
        else:
            directory = os.path.expanduser('~')
        file = ""
    filePicker = context.ServiceManager.createInstanceWithContext(
        "com.sun.star.ui.dialogs.OfficeFilePicker",
        context
    )
    filePicker.setTitle(title)
    pickerType = uno.getConstantByName(
        "com.sun.star.ui.dialogs.TemplateDescription.FILEOPEN_SIMPLE"
    )
    filePicker.initialize((pickerType,))
    filePicker.setDisplayDirectory(
        uno.systemPathToFileUrl(directory)
    )
    filePicker.setDefaultName(file)
    for filterTitle, filterValue in fileFilters.items():
        filePicker.appendFilter(filterTitle, filterValue)
        if not filePicker.getCurrentFilter():
            # Установить первый фильтр в качестве фильтра по умолчанию.
            filePicker.setCurrentFilter(filterTitle)
    result = filePicker.execute()
    OK = uno.getConstantByName(
        "com.sun.star.ui.dialogs.ExecutableDialogResults.OK"
    )
    if result == OK:
        sourcePath = uno.fileUrlToSystemPath(filePicker.Files[0])
        return sourcePath
    return None

def getSourceFileName():
    """Получить имя файла с данными о схеме.

    Попытаться найти файл с данными о схеме в текущем каталоге.
    В случае неудачи, показать диалоговое окно выбора файла.

    Для KiCad источником данных о схеме является список цепей.

    Возвращаемое значение -- полное имя файла или None, если файл
        не найден или не выбран.

    """
    sourcePath = config.get("doc", "source")
    if os.path.exists(sourcePath):
        return sourcePath
    sourceDir = ""
    sourceName = ""
    docUrl = XSCRIPTCONTEXT.getDocument().URL
    if docUrl:
        docPath = uno.fileUrlToSystemPath(docUrl)
        sourceDir = os.path.dirname(docPath)
        for fileName in os.listdir(sourceDir):
            if fileName.endswith(".pro"):
                sourceName = fileName.replace(".pro", ".net")
        if sourceName:
            sourcePath = os.path.join(sourceDir, sourceName)
            if os.path.exists(sourcePath):
                config.set("doc", "source", sourcePath)
                config.save()
                return sourcePath
    sourcePath = showFilePicker(
        os.path.join(sourceDir, sourceName),
        **{"Список цепей KiCad": "*.net;*.xml", "Все файлы": "*.*"}
    )
    if sourcePath is not None:
        config.set("doc", "source", sourcePath)
        config.save()
        return sourcePath
    return None

def getSchematicData():
    """Подготовить необходимые данные о схеме.

    Выбрать из файла данные о компонентах и данные для заполнения
    основной надписи.

    Возвращаемое значение -- объект класса Schematic или None, если
        файл не найден или данные в файле отсутствуют.

    """
    sourceFileName = getSourceFileName()
    if sourceFileName is None:
        # Отменено пользователем
        #showMessage(
        #    "Не удалось получить данные о схеме.",
        #    "Ведомость покупных изделий"
        #)
        return None
    try:
        return schematic.Schematic(sourceFileName)
    except kicadnet.ParseException as error:
        showMessage(
            "Не удалось получить данные о схеме.\n\n" \
            "При разборе файла обнаружена ошибка:\n" \
            + str(error),
            "Ведомость покупных изделий"
        )
    except:
        showMessage(
            "Не удалось получить данные о схеме.\n\n" \
            + traceback.format_exc(),
            "Ведомость покупных изделий"
        )
    return None

def getSchematicInfo():
    """Считать формат листа и децимальный номер из файла схемы.

    Файл схемы определяется на основе имени выбранного файла списка цепей.
    Изымаются только данные о формате листа и децимальный номер (комментарий 1).

    Возвращаемое значение -- кортеж с двумя значениями:
        (формат листа, децимальный номер).

    """
    try:
        sourcePath = config.get("doc", "source")
        schPath = os.path.splitext(sourcePath)[0] + ".sch"
        size = ""
        number = ""
        if os.path.exists(schPath):
            with open(schPath, encoding="utf-8") as schematic:
                sizePattern = r"^\$Descr ([^\s]+) \d.*$"
                numberPattern = r"^Comment1 \"(.*)\"$"
                for line in schematic:
                    if re.match(sizePattern, line):
                        size = re.search(sizePattern, line).group(1)
                    elif re.match(numberPattern, line):
                        number = re.search(numberPattern, line).group(1)
                        break
        return (size, number)
    except:
        return ("", "")

def getPcbInfo():
    """Считать формат листа и децимальный номер из файла печатной платы.

    Файл схемы определяется на основе имени выбранного файла списка цепей.
    Изымаются только данные о формате листа и децимальный номер (комментарий 1).

    Возвращаемое значение -- кортеж с двумя значениями:
        (формат листа, децимальный номер).

    """
    try:
        sourcePath = config.get("doc", "source")
        pcbPath = os.path.splitext(sourcePath)[0] + ".kicad_pcb"
        size = ""
        number = ""
        if os.path.exists(pcbPath):
            with open(pcbPath, encoding="utf-8") as pcb:
                sizePattern = r"^\s*\(page \"?([^\s\"]+)\"?(?: portrait)?\)$"
                numberPattern = r"^\s*\(comment 1 \"(.*)\"\)$"
                for line in pcb:
                    if re.match(sizePattern, line):
                        size = re.search(sizePattern, line).group(1)
                    elif re.match(numberPattern, line):
                        number = re.search(numberPattern, line).group(1)
                        break
        return (size, number)
    except:
        return ("", "")

def getFirstPageInfo():
    """Информация о первом листе.

    Возвращаемое значение -- кортеж из трёх значений:
        (номер варианта первого листа,
         кол. строк на первом листе,
         кол. строк на последующих листах)

    """
    doc = XSCRIPTCONTEXT.getDocument()
    firstPageStyleName = doc.Text.createTextCursor().PageDescName
    if firstPageStyleName.startswith("Первый лист "):
        firstPageVariant = firstPageStyleName[-1]
        firstRowCount = 28 if firstPageVariant in "12" else 25
        otherRowCount = 30
        return (firstPageVariant, firstRowCount, otherRowCount)
    return ("?", 0, 0)

def getTableRowHeight(rowIndex):
    """Вычислить высоту строки основной таблицы.

    Высота строк подбирается так, чтобы нижнее обрамление последней строки
    листа совпадало с верхней линией основной надписи.

    Аргументы:

    rowIndex -- номер строки.

    Возвращаемое значение -- высота строки таблицы.

    """
    height = 800
    firstPageVariant, firstRowCount, otherRowCount = getFirstPageInfo()
    if firstPageVariant == "?":
        return height
    if rowIndex <= firstRowCount:
        if firstPageVariant in "12":
            # без граф заказчика:
                if rowIndex == firstRowCount:
                    height = 822
                else:
                    height = 813
        else:
            # с графами заказчика:
            height = 824
    elif (rowIndex - firstRowCount) % otherRowCount == 0:
        height = 829
    else:
        height = 815
    return height

def updateTableRowsHeight():
    """Обновить высоту строк таблицы.

    Высота строк подстраивается так, чтобы нижнее обрамление последней строки
    листа совпадало с верхней линией основной надписи.

    """
    doc = XSCRIPTCONTEXT.getDocument()
    if "Ведомость_покупных_изделий" not in doc.TextTables:
        return
    table = doc.TextTables["Ведомость_покупных_изделий"]
    doc.lockControllers()
    for rowIndex in range(2, table.Rows.Count):
        table.Rows[rowIndex].Height = getTableRowHeight(rowIndex)
    doc.unlockControllers()

def rebuildTable():
    """Построить новую пустую таблицу."""
    global SKIP_MODIFY_EVENTS
    SKIP_MODIFY_EVENTS = True
    doc = XSCRIPTCONTEXT.getDocument()
    doc.lockControllers()
    doc.UndoManager.lock()
    text = doc.Text
    cursor = text.createTextCursor()
    firstPageStyleName = cursor.PageDescName
    text.String = ""
    cursor.ParaStyleName = "Пустой"
    if firstPageStyleName in ("Первый лист 1", "Первый лист 2", "Первый лист 3", "Первый лист 4"):
        cursor.PageDescName = firstPageStyleName
    else:
        cursor.PageDescName = "Первый лист 1"
    # Если не оставить параграф перед таблицей, то при изменении форматирования
    # в ячейках с автоматическими стилями будет сбрасываться стиль страницы на
    # стиль по умолчанию.
    text.insertControlCharacter(
        cursor,
        uno.getConstantByName(
            "com.sun.star.text.ControlCharacter.PARAGRAPH_BREAK"
        ),
        False
    )
    # Таблица
    table = doc.createInstance("com.sun.star.text.TextTable")
    table.initialize(3, 11)
    text.insertTextContent(text.End, table, False)
    table.Name = "Ведомость_покупных_изделий"
    table.HoriOrient = uno.getConstantByName("com.sun.star.text.HoriOrientation.LEFT_AND_WIDTH")
    table.Width = 39500
    table.LeftMargin = 2000
    columnSeparators = table.TableColumnSeparators
    columnSeparators[0].Position = 177   # int((7)/395*10000)
    columnSeparators[1].Position = 1695  # int((7+60)/395*10000)
    columnSeparators[2].Position = 2834  # int((7+60+45)/395*10000)
    columnSeparators[3].Position = 4606  # int((7+60+45+70)/395*10000)
    columnSeparators[4].Position = 5998  # int((7+60+45+70+55)/395*10000)
    columnSeparators[5].Position = 7770  # int((7+60+45+70+55+70)/395*10000)
    columnSeparators[6].Position = 8175  # int((7+60+45+70+55+70+16)/395*10000)
    columnSeparators[7].Position = 8580  # int((7+60+45+70+55+70+16+16)/395*10000)
    columnSeparators[8].Position = 8985  # int((7+60+45+70+55+70+16+16+16)/395*10000)
    columnSeparators[9].Position = 9390  # int((7+60+45+70+55+70+16+16+16+16)/395*10000)
    table.TableColumnSeparators = columnSeparators
    # Обрамление
    border = table.TableBorder
    noLine = uno.createUnoStruct("com.sun.star.table.BorderLine")
    normalLine = uno.createUnoStruct("com.sun.star.table.BorderLine")
    normalLine.OuterLineWidth = 50
    border.TopLine = noLine
    border.LeftLine = noLine
    border.RightLine = noLine
    border.BottomLine = normalLine
    border.HorizontalLine = normalLine
    border.VerticalLine = normalLine
    table.TableBorder = border
    # Заголовок
    table.RepeatHeadline = True
    table.HeaderRowCount = 2
    table.Rows[0].Height = 900
    table.Rows[0].IsAutoHeight = False
    table.Rows[1].Height = 1800
    table.Rows[1].IsAutoHeight = False
    cellCursor = table.createCursorByCellName("A1")
    cellCursor.gotoCellByName("A2", True)
    cellCursor.mergeRange()
    cellCursor.gotoCellByName("B1", False)
    cellCursor.gotoCellByName("B2", True)
    cellCursor.mergeRange()
    cellCursor.gotoCellByName("C1", False)
    cellCursor.gotoCellByName("C2", True)
    cellCursor.mergeRange()
    cellCursor.gotoCellByName("D1", False)
    cellCursor.gotoCellByName("D2", True)
    cellCursor.mergeRange()
    cellCursor.gotoCellByName("E1", False)
    cellCursor.gotoCellByName("E2", True)
    cellCursor.mergeRange()
    cellCursor.gotoCellByName("F1", False)
    cellCursor.gotoCellByName("F2", True)
    cellCursor.mergeRange()
    cellCursor.gotoCellByName("G1", False)
    cellCursor.gotoCellByName("J1", True)
    cellCursor.mergeRange()
    cellCursor.gotoCellByName("H1", False)
    cellCursor.gotoCellByName("K2", True)
    cellCursor.mergeRange()
    headerNames = (
        ("A1", "№ строки"),
        ("B1", "Наименование"),
        ("C1", "Код\nпродукции"),
        ("D1", "Обозначение\nдокумента на\nпоставку"),
        ("E1", "Поставщик"),
        ("F1", "Куда входит\n(обозначение)"),
        ("G1", "Количество"),
        ("G2", "на из-\nделие"),
        ("H2", "в ком-\nплекты"),
        ("I2", "на ре-\nгулир."),
        ("J2", "всего"),
        ("H1", "Приме-\nчание")
    )
    for cellName, headerName in headerNames:
        cell = table.getCellByName(cellName)
        cellCursor = cell.createTextCursor()
        cellCursor.ParaStyleName = "Заголовок графы таблицы"
        cell.TopBorderDistance = 50
        cell.BottomBorderDistance = 50
        cell.LeftBorderDistance = 50
        cell.RightBorderDistance = 50
        cell.VertOrient = uno.getConstantByName(
            "com.sun.star.text.VertOrientation.CENTER"
        )
        if cellName.endswith("1"):
            cellCursor.CharHeight = 18
        if cellName == "A1":
            cellCursor.CharRotation = 900
            cell.LeftBorderDistance = 0
            cell.RightBorderDistance = 100
        cell.String = headerName
    # Строки
    table.Rows[2].Height = getTableRowHeight(2)
    table.Rows[2].IsAutoHeight = False
    cellStyles = (
        ("A3", "№ строки"),
        ("B3", "Наименование"),
        ("C3", "Код продукции"),
        ("D3", "Обозначение документа на поставку"),
        ("E3", "Поставщик"),
        ("F3", "Куда входит (обозначение)"),
        ("G3", "Кол. на изделие"),
        ("H3", "Кол. в комплекты"),
        ("I3", "Кол. на регулир."),
        ("J3", "Кол. всего"),
        ("K3", "Примечание")
    )
    for cellName, cellStyle in cellStyles:
        cell = table.getCellByName(cellName)
        cursor = cell.createTextCursor()
        cursor.ParaStyleName = cellStyle
        cell.TopBorderDistance = 0
        cell.BottomBorderDistance = 0
        cell.LeftBorderDistance = 50
        cell.RightBorderDistance = 50
        cell.VertOrient = uno.getConstantByName(
            "com.sun.star.text.VertOrientation.CENTER"
        )
    doc.refresh()
    viewCursor = doc.CurrentController.ViewCursor
    viewCursor.gotoRange(table.getCellByName("A3").Start, False)
    doc.UndoManager.unlock()
    doc.UndoManager.clear()
    doc.unlockControllers()
    SKIP_MODIFY_EVENTS = False

def appendRevTable():
    """Добавить таблицу регистрации изменений."""
    doc = XSCRIPTCONTEXT.getDocument()
    if "Лист_регистрации_изменений" in doc.TextTables:
        return
    global SKIP_MODIFY_EVENTS
    SKIP_MODIFY_EVENTS = True
    doc.lockControllers()
    doc.UndoManager.lock()
    text = doc.Text
    text.insertControlCharacter(
        text.End,
        uno.getConstantByName(
            "com.sun.star.text.ControlCharacter.PARAGRAPH_BREAK"
        ),
        False
    )
    # Таблица
    table = doc.createInstance("com.sun.star.text.TextTable")
    table.initialize(4, 10)
    text.insertTextContent(text.End, table, False)
    table.Name = "Лист_регистрации_изменений"
    table.BreakType = uno.Enum("com.sun.star.style.BreakType", "PAGE_BEFORE")
    table.PageDescName = "Лист регистрации изменений"
    table.HoriOrient = uno.getConstantByName("com.sun.star.text.HoriOrientation.LEFT_AND_WIDTH")
    table.Width = 18500
    table.LeftMargin = 2000
    columnSeparators = table.TableColumnSeparators
    columnSeparators[0].Position = 432   # int((8)/185*10000)
    columnSeparators[1].Position = 1512  # int((8+20)/185*10000)
    columnSeparators[2].Position = 2594  # int((8+20+20)/185*10000)
    columnSeparators[3].Position = 3675  # int((8+20+20+20)/185*10000)
    columnSeparators[4].Position = 4756  # int((8+20+20+20+20)/185*10000)
    columnSeparators[5].Position = 5837  # int((8+20+20+20+20+20)/185*10000)
    columnSeparators[6].Position = 7189  # int((8+20+20+20+20+20+25)/185*10000)
    columnSeparators[7].Position = 8540  # int((8+20+20+20+20+20+25+25)/185*10000)
    columnSeparators[8].Position = 9351  # int((8+20+20+20+20+20+25+25+15)/185*10000)
    table.TableColumnSeparators = columnSeparators
    # Заголовок
    table.RepeatHeadline = True
    table.HeaderRowCount = 3
    table.Rows[0].Height = 1030
    table.Rows[0].IsAutoHeight = False
    table.Rows[1].Height = 600
    table.Rows[1].IsAutoHeight = False
    table.Rows[2].Height = 1900
    table.Rows[2].IsAutoHeight = False
    cellCursor = table.createCursorByCellName("A1")
    cellCursor.gotoCellByName("J1", True)
    cellCursor.mergeRange()
    cellCursor.gotoCellByName("A2", False)
    cellCursor.gotoCellByName("E2", True)
    cellCursor.mergeRange()
    cellCursor.gotoCellByName("B2", False)
    cellCursor.gotoCellByName("F3", True)
    cellCursor.mergeRange()
    cellCursor.gotoCellByName("C2", False)
    cellCursor.gotoCellByName("G3", True)
    cellCursor.mergeRange()
    cellCursor.gotoCellByName("D2", False)
    cellCursor.gotoCellByName("H3", True)
    cellCursor.mergeRange()
    cellCursor.gotoCellByName("E2", False)
    cellCursor.gotoCellByName("I3", True)
    cellCursor.mergeRange()
    cellCursor.gotoCellByName("F2", False)
    cellCursor.gotoCellByName("J3", True)
    cellCursor.mergeRange()
    headerNames = (
        ("A1", "Лист регистрации изменений"),
        ("A2", "Номера листов (страниц)"),
        ("B2", "Всего\nлистов\n(страниц)\nв докум."),
        ("C2", "№\nдокумен-\nта"),
        ("D2", "Входящий\n№ сопрово-\nдительно-\nго докум.\nи дата"),
        ("E2", "Подп."),
        ("F2", "Да-\nта"),
        ("A3", "Изм."),
        ("B3", "изменен-\nных"),
        ("C3", "заменен-\nных"),
        ("D3", "новых"),
        ("E3", "аннули-\nрован-\nных")
    )
    for cellName, headerName in headerNames:
        cell = table.getCellByName(cellName)
        cellCursor = cell.createTextCursor()
        cellCursor.ParaStyleName = "Заголовок графы таблицы"
        fontSize = 16
        if cellName == "A1":
            fontSize = 18
        cellCursor.CharHeight = fontSize
        cellCursor.ParaAdjust = uno.Enum(
            "com.sun.star.style.ParagraphAdjust",
            "CENTER"
        )
        if cellName == "D2":
            lineSpacing = cellCursor.ParaLineSpacing
            lineSpacing.Mode = uno.getConstantByName(
                "com.sun.star.style.LineSpacingMode.FIX"
            )
            lineSpacing.Height = 490
            cellCursor.ParaLineSpacing = lineSpacing
        if cellName == "A3":
            cellCursor.CharScaleWidth = 85
        cell.TopBorderDistance = 0
        cell.BottomBorderDistance = 0
        cell.LeftBorderDistance = 0
        cell.RightBorderDistance = 0
        cell.VertOrient = uno.getConstantByName(
            "com.sun.star.text.VertOrientation.CENTER"
        )
        cell.String = headerName
    # Обрамление
    border = table.TableBorder
    noLine = uno.createUnoStruct("com.sun.star.table.BorderLine")
    normalLine = uno.createUnoStruct("com.sun.star.table.BorderLine")
    normalLine.OuterLineWidth = 50
    border.TopLine = noLine
    border.LeftLine = noLine
    border.RightLine = noLine
    border.BottomLine = normalLine
    border.HorizontalLine = normalLine
    border.VerticalLine = normalLine
    table.TableBorder = border
    # Строки
    table.Rows[3].Height = 815
    table.Rows[3].IsAutoHeight = False
    for i in range(10):
        cell = table.getCellByPosition(i, 3)
        cursor = cell.createTextCursor()
        cursor.ParaStyleName = "Значение графы таблицы"
        cell.TopBorderDistance = 0
        cell.BottomBorderDistance = 0
        cell.LeftBorderDistance = 50
        cell.RightBorderDistance = 50
        cell.VertOrient = uno.getConstantByName(
            "com.sun.star.text.VertOrientation.CENTER"
        )
    table.Rows.insertByIndex(3, 28)
    # Дабы избежать образования пустой страницы после листа рег.изм.
    cursor = text.createTextCursor()
    cursor.gotoEnd(False)
    cursor.ParaStyleName = "Пустой"
    doc.refresh()
    viewCursor = doc.CurrentController.ViewCursor
    viewCursor.gotoRange(table.getCellByName("A4").Start, False)
    doc.UndoManager.unlock()
    doc.UndoManager.clear()
    doc.unlockControllers()
    SKIP_MODIFY_EVENTS = False
    return

def removeRevTable():
    """Удалить таблицу регистрации изменений."""
    doc = XSCRIPTCONTEXT.getDocument()
    if "Лист_регистрации_изменений" not in doc.TextTables:
        return
    global SKIP_MODIFY_EVENTS
    SKIP_MODIFY_EVENTS = True
    doc.lockControllers()
    doc.UndoManager.lock()
    doc.TextTables["Лист_регистрации_изменений"].dispose()
    cursor = doc.Text.createTextCursor()
    cursor.gotoEnd(False)
    cursor.goLeft(1, True)
    cursor.String = ""
    doc.refresh()
    if "Ведомость_покупных_изделий" in doc.TextTables:
        viewCursor = doc.CurrentController.ViewCursor
        table = doc.TextTables["Ведомость_покупных_изделий"]
        viewCursor.gotoRange(table.getCellByName("A3").Start, False)
    doc.UndoManager.unlock()
    doc.UndoManager.clear()
    doc.unlockControllers()
    SKIP_MODIFY_EVENTS = False
    return

def syncCommonFields():
    """Обновить значения общих граф.

    Обновить значения граф форматной рамки последующих листов, которые
    совпадают с графами форматной рамки и основной надписи первого листа.
    Необходимость в обновлении возникает при изменении значения графы
    на первом листе.
    На втором и последующих листах эти графы защищены от записи.

    """
    doc = XSCRIPTCONTEXT.getDocument()
    doc.UndoManager.lock()
    doc.lockControllers()
    for name in STAMP_COMMON_FIELDS:
        if ("Перв.1: " + name) not in doc.TextFrames:
            continue
        firstFrame = doc.TextFrames["Перв.1: " + name]
        for prefix in ("Прочие: ", "РегИзм: "):
            if (prefix + name) not in doc.TextFrames:
                continue
            otherFrame = doc.TextFrames[prefix + name]
            otherFrame.String = firstFrame.String

            firstCursor = firstFrame.createTextCursor()
            otherCursor = otherFrame.createTextCursor()
            otherCursor.gotoEnd(True)
            otherCursor.CharHeight = firstCursor.CharHeight
            if name == "2 Обозначение документа":
                # На первом листе ширина графы 120 мм, а на последующих -- 110.
                otherCursor.CharScaleWidth = textwidth.getWidthFactor(
                    otherFrame.String,
                    otherCursor.CharHeight,
                    109
                )
            else:
                otherCursor.CharScaleWidth = firstCursor.CharScaleWidth
    doc.unlockControllers()
    doc.UndoManager.unlock()

def addPageRevTable():
    """Добавить таблицу изменений на текущем листе."""
    doc = XSCRIPTCONTEXT.getDocument()
    pageNum = doc.CurrentController.ViewCursor.Page
    pageStyle = doc.CurrentController.ViewCursor.PageStyleName
    if not pageStyle.startswith("Первый лист") \
            and pageStyle not in ("Последующие листы", "Лист регистрации изменений"):
        return
    global SKIP_MODIFY_EVENTS
    SKIP_MODIFY_EVENTS = True
    doc.lockControllers()
    doc.UndoManager.lock()

    # Врезка
    frame = doc.createInstance("com.sun.star.text.TextFrame")
    frame.Name = "Изм_стр_%d" % pageNum
    doc.Text.insertTextContent(doc.Text.End, frame, False)
    frame.AnchorType = uno.Enum("com.sun.star.text.TextContentAnchorType", "AT_PAGE")
    frame.AnchorPageNo = pageNum
    # Обрамление
    noLine = uno.createUnoStruct("com.sun.star.table.BorderLine")
    frame.LeftBorder = noLine
    frame.RightBorder = noLine
    frame.TopBorder = noLine
    frame.BottomBorder = noLine
    frame.BorderDistance = 0
    frame.LeftMargin = 0
    frame.RightMargin = 0
    frame.TopMargin = 0
    frame.BottomMargin = 0
    # Размер и расположение
    frame.HoriOrient = uno.getConstantByName("com.sun.star.text.HoriOrientation.NONE")
    frame.VertOrient = uno.getConstantByName("com.sun.star.text.VertOrientation.NONE")
    frame.HoriOrientRelation = 0 # Frame
    frame.VertOrientRelation = 0 # Frame
    if pageStyle == "Лист регистрации изменений":
        frame.HoriOrientPosition = 2000
        frame.VertOrientPosition = 27700
    elif pageStyle == "Последующие листы":
        frame.HoriOrientPosition = 23000
        frame.VertOrientPosition = 27700
    else: # Первый лист
        frame.HoriOrientPosition = 23000
        frame.VertOrientPosition = 25200
    frame.Height = 1000
    frame.Width = 6500
    frame.PositionProtected = True
    frame.SizeProtected = True

    # Таблица
    table = doc.createInstance("com.sun.star.text.TextTable")
    table.initialize(2, 5)
    frame.Text.insertTextContent(frame.Text.End, table, False)
    table.Name = "Изм_таб_%d" % pageNum
    table.HoriOrient = uno.getConstantByName("com.sun.star.text.HoriOrientation.LEFT_AND_WIDTH")
    table.Width = 6500
    table.LeftMargin = 0
    table.Rows[0].Height = 500
    table.Rows[0].IsAutoHeight = False
    table.Rows[1].Height = 500
    table.Rows[1].IsAutoHeight = False
    columnSeparators = table.TableColumnSeparators
    columnSeparators[0].Position = 1076  # int((7)/65*10000)
    columnSeparators[1].Position = 2615  # int((7+10)/65*10000)
    columnSeparators[2].Position = 6153  # int((7+10+23)/65*10000)
    columnSeparators[3].Position = 8461  # int((7+10+23+15)/65*10000)
    table.TableColumnSeparators = columnSeparators
    for j in range(2):
        for i in range(5):
            cell = table.getCellByPosition(i, j)
            cursor = cell.createTextCursor()
            cursor.ParaStyleName = "Значение графы форматной рамки"
            cell.TopBorderDistance = 0
            cell.BottomBorderDistance = 0
            cell.LeftBorderDistance = 0
            cell.RightBorderDistance = 0
            cell.VertOrient = uno.getConstantByName(
                "com.sun.star.text.VertOrientation.CENTER"
            )
    # Обрамление
    border = table.TableBorder
    noLine = uno.createUnoStruct("com.sun.star.table.BorderLine")
    border.TopLine = noLine
    border.LeftLine = noLine
    border.RightLine = noLine
    border.BottomLine = noLine
    border.HorizontalLine = noLine
    border.VerticalLine = noLine
    table.TableBorder = border
    doc.refresh()
    viewCursor = doc.CurrentController.ViewCursor
    viewCursor.gotoRange(table.getCellByName("A2").Start, False)
    doc.UndoManager.unlock()
    doc.UndoManager.clear()
    doc.unlockControllers()
    SKIP_MODIFY_EVENTS = False
    return

def removePageRevTable():
    """Удалить таблицу изменений на текущем листе."""
    doc = XSCRIPTCONTEXT.getDocument()
    frame = doc.CurrentController.Frame
    pageNum = doc.CurrentController.ViewCursor.Page
    if ("Изм_стр_%d" % pageNum) not in doc.TextFrames:
        return
    global SKIP_MODIFY_EVENTS
    SKIP_MODIFY_EVENTS = True
    isEmpty = True
    for j in range(2):
        for i in range(5):
            cell = doc.TextTables["Изм_таб_%d" % pageNum].getCellByPosition(i, j)
            if cell.String != "":
                isEmpty = False
                viewCursor = doc.CurrentController.ViewCursor
                viewCursor.gotoRange(cell.Start, False)
                doc.refresh()
                break
    doRemove = True
    if not isEmpty:
        msgbox = frame.ContainerWindow.Toolkit.createMessageBox(
            frame.ContainerWindow,
            uno.Enum("com.sun.star.awt.MessageBoxType", "MESSAGEBOX"),
            uno.getConstantByName("com.sun.star.awt.MessageBoxButtons.BUTTONS_YES_NO"),
            "Внимание!",
            "Таблица с изменениями не пуста.\n"
            "Удалить?"
        )
        yes = uno.getConstantByName("com.sun.star.awt.MessageBoxResults.YES")
        result = msgbox.execute()
        if result != yes:
            doRemove = False
    if doRemove:
        if not isEmpty:
            viewCursor = doc.CurrentController.ViewCursor
            viewCursor.jumpToEndOfPage()
            doc.refresh()
        doc.lockControllers()
        doc.UndoManager.lock()
        doc.TextTables["Изм_таб_%d" % pageNum].dispose()
        doc.TextFrames["Изм_стр_%d" % pageNum].dispose()
        doc.UndoManager.unlock()
        doc.UndoManager.clear()
        doc.unlockControllers()
    SKIP_MODIFY_EVENTS = False
    return
