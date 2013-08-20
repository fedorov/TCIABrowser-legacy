import os, dicom
import unittest
from __main__ import vtk, qt, ctk, slicer, string, glob
import urllib2, urllib

#
# TCIAClient: helper class for API calls
#
class TCIAClient:
    def __init__(self, apiKey):
        self.apiKey = apiKey


    def execute(self, baseUrl, queryParameters={}):
        headers = {"api_key" : self.apiKey }
        queryString = "?%s" % urllib.urlencode(queryParameters);
        requestUrl = baseUrl + queryString
        request = urllib2.Request(url=requestUrl , headers=headers)
        resp = urllib2.urlopen(request);
        return resp

#
# TCIABrowser
#

class TCIABrowser:
  def __init__(self, parent):
    parent.title = "TCIABrowser" # TODO make this more human readable by adding spaces
    parent.categories = ["Informatics"]
    parent.dependencies = []
    parent.contributors = ["Andrey Fedorov (SPL)"] # replace with "Firstname Lastname (Org)"
    parent.helpText = """
    """
    parent.acknowledgementText = """
    Supported by NIH U01CA151261 (PI Fennessy)
""" # replace with organization, grant and thanks.
    self.parent = parent

    # Add this test to the SelfTest module's list for discovery when the module
    # is created.  Since this module may be discovered before SelfTests itself,
    # create the list if it doesn't already exist.
    try:
      slicer.selfTests
    except AttributeError:
      slicer.selfTests = {}
    slicer.selfTests['TCIABrowser'] = self.runTest

  def runTest(self):
    tester = TCIABrowserTest()
    tester.runTest()


#
# qTCIABrowserWidget
#

class TCIABrowserWidget:
  def __init__(self, parent = None):
    if not parent:
      self.parent = slicer.qMRMLWidget()
      self.parent.setLayout(qt.QVBoxLayout())
      self.parent.setMRMLScene(slicer.mrmlScene)
    else:
      self.parent = parent
    self.layout = self.parent.layout()
    if not parent:
      self.setup()
      self.parent.show()

    # module-specific initialization
    self.inputDataDir = ''

    # setup API key
    keyFile = open('/Users/fedorov/tcia_api.key','r')
    self.key = keyFile.readline()[:-1]
    self.queryBaseURL = "https://services.cancerimagingarchive.net/services/TCIA/TCIA/query/"

    # setup the TCIA client
    self.TCIAClient = TCIAClient(self.key)



  def setup(self):
    # Instantiate and connect widgets ...

    #
    # Reload and Test area
    #
    reloadCollapsibleButton = ctk.ctkCollapsibleButton()
    reloadCollapsibleButton.text = "Reload && Test"
    self.layout.addWidget(reloadCollapsibleButton)
    reloadFormLayout = qt.QFormLayout(reloadCollapsibleButton)

    # reload button
    # (use this during development, but remove it when delivering
    #  your module to users)
    self.reloadButton = qt.QPushButton("Reload")
    self.reloadButton.toolTip = "Reload this module."
    self.reloadButton.name = "TCIABrowser Reload"
    reloadFormLayout.addWidget(self.reloadButton)
    self.reloadButton.connect('clicked()', self.onReload)

    # reload and test button
    # (use this during development, but remove it when delivering
    #  your module to users)
    self.reloadAndTestButton = qt.QPushButton("Reload and Test")
    self.reloadAndTestButton.toolTip = "Reload this module and then run the self tests."
    reloadFormLayout.addWidget(self.reloadAndTestButton)
    self.reloadAndTestButton.connect('clicked()', self.onReloadAndTest)

    #
    # Step 1: selection of the data directory
    #
    self.collectionSelector = qt.QComboBox()
    self.layout.addWidget(self.collectionSelector)
    self.collectionSelector.connect('currentIndexChanged(QString)',self.collectionSelected)

    self.studyTable = ItemTable(self.parent,headerName='Study Name')
    self.layout.addWidget(self.studyTable.widget)
    self.studyTable.widget.connect('cellClicked(int,int)',self.onStudyCellClicked)

    self.seriesTable = ItemTable(self.parent,headerName="Series Name")
    self.layout.addWidget(self.seriesTable.widget)

    self.loadButton = qt.QPushButton('Load series')
    self.layout.addWidget(self.loadButton)
    self.loadButton.connect('clicked()',self.onLoadButtonClicked)

    # Add vertical spacer
    self.layout.addStretch(1)

    # set up temporary directory
    self.tempDir = slicer.app.temporaryPath+'/TCIABrowser-tmp'
    print('Temporary directory location: '+self.tempDir)
    qt.QDir().mkpath(self.tempDir)

  def enter(self):
    # query the list of all collections and populate collection selector
    print('in enter()')
    response = self.TCIAClient.execute(baseUrl=self.queryBaseURL+'getCollectionValues')
    if response.getcode() == 200:
      print('Success')
      responseStr = response.read()[:-1]
      print(responseStr)

      collections = string.split(responseStr,'\n')
      print(str(collections))
      collections = collections[1:]
      for c in collections:
        self.collectionSelector.addItem(c[1:-1])

  def collectionSelected(self,item):
    print('Current item:'+str(item))
    self.collection = item
    response = self.TCIAClient.execute(baseUrl=self.queryBaseURL+'getPatientStudy',queryParameters={"collection":item})
    if response.getcode() == 200:
      studiesStr = response.read()
      studies = string.split(studiesStr,'\n')
      print('Response items:',studies[0])
      self.studyTable.setHeader(string.split(studies[0],','))
      print(studies[1])
      studies = studies[1:]
      #print(str(studies))
      self.patientIDs = []
      for s in studies:
        #print('Study row:',s)
        items = string.split(s,',')
        if len(items)>6:
          self.patientIDs.append(items[6])

      self.studyTable.setContent(studies)

  def onStudyCellClicked(self,row,col):
    print('Study cell clicked')
    self.study = self.studyTable.getSelectedItem().text()
    response = self.TCIAClient.execute(baseUrl=self.queryBaseURL+'getSeries',queryParameters={'collection':self.collection,'study_instance_uid':self.study})
    if response.getcode() == 200:
      seriesStr = response.read()
      series = string.split(seriesStr,'\n')
      self.seriesTable.setHeader(string.split(series[0],','))
      series = series[1:]
      print('Response series:'+str(series))
      self.seriesTable.setContent(series)

  def onLoadButtonClicked(self):
    try:
      self.series = self.seriesTable.getSelectedItem().text()
      print('Series selected: '+self.series)
    except:
      print('No text!')
      return
    response = self.TCIAClient.execute(baseUrl=self.queryBaseURL+'getImage',queryParameters={'series_instance_uid':self.series})
    if response.getcode() == 200:
      seriesZip = open(self.tempDir+'/series.zip','wb')
      seriesZip.write(response.read())
      seriesZip.close()
      import zipfile
      zfile = zipfile.ZipFile(self.tempDir+'/series.zip')
      print('File received')
      self.cleanupDir(self.tempDir+'/images')
      try:
        os.mkdir(self.tempDir+'/images')
      except:
        pass

      print('Series '+self.series+' fetched')

      for zf in zfile.namelist():
        if string.find(zf,'.dcm')>0:
          # found a dicom file, will extract
          fname = os.path.split(zf)[-1]
          print('Extracting '+fname)
          extracted = open(self.tempDir+'/images/'+fname,'wb')
          extracted.write(zfile.read(zf))
          extracted.close()

      zfile.close()

      dicomPlugin = slicer.modules.dicomPlugins['DICOMScalarVolumePlugin']()
      files = glob.glob(self.tempDir+'/images/*.dcm')
      allLoadables = dicomPlugin.examine([files])
      selectedLoadables = []

      for sv in allLoadables:
        if sv.selected:
          selectedLoadables.append(sv)
          volume = dicomPlugin.load(sv)
          # volume.SetName(text)
          #self.volumeNodes[seriesNumber] = volume
          #if string.find(text, 'T2')>0 and string.find(text, 'AX')>0:
          #  print('Setting reference to '+text)
          #  ref = seriesNumber
      # print('Have this many loadables for series '+str(seriesNumber)+' : '+str(len(selectedLoadables)))



  def delayDisplay(self,message,msec=1000):
    """This utility method displays a small dialog and waits.
    This does two things: 1) it lets the event loop catch up
    to the state of the test so that rendering and widget updates
    have all taken place before the test continues and 2) it
    shows the user/developer/tester the state of the test
    so that we'll know when it breaks.
    """
    print(message)
    self.info = qt.QDialog()
    self.infoLayout = qt.QVBoxLayout()
    self.info.setLayout(self.infoLayout)
    self.label = qt.QLabel(message,self.info)
    self.infoLayout.addWidget(self.label)
    qt.QTimer.singleShot(msec, self.info.close)
    self.info.exec_()

  def cleanupDir(self, d):
    if not os.path.exists(d):
      return
    oldFiles = os.listdir(d)
    for f in oldFiles:
      path = d+'/'+f
      if not os.path.isdir(path):
        os.unlink(d+'/'+f)

  def onReload(self,moduleName="TCIABrowser"):
    """Generic reload method for any scripted module.
    ModuleWizard will subsitute correct default moduleName.
    """
    import imp, sys, os, slicer, CompareVolumes, dicom, string

    widgetName = moduleName + "Widget"

    # reload the source code
    # - set source file path
    # - load the module to the global space
    filePath = eval('slicer.modules.%s.path' % moduleName.lower())
    p = os.path.dirname(filePath)
    if not sys.path.__contains__(p):
      sys.path.insert(0,p)
    fp = open(filePath, "r")
    globals()[moduleName] = imp.load_module(
        moduleName, fp, filePath, ('.py', 'r', imp.PY_SOURCE))
    fp.close()

    # rebuild the widget
    # - find and hide the existing widget
    # - create a new widget in the existing parent
    parent = slicer.util.findChildren(name='%s Reload' % moduleName)[0].parent().parent()
    for child in parent.children():
      try:
        child.hide()
      except AttributeError:
        pass
    # Remove spacer items
    item = parent.layout().itemAt(0)
    while item:
      parent.layout().removeItem(item)
      item = parent.layout().itemAt(0)
    # create new widget inside existing parent
    globals()[widgetName.lower()] = eval(
        'globals()["%s"].%s(parent)' % (moduleName, widgetName))
    globals()[widgetName.lower()].setup()

  def onReloadAndTest(self,moduleName="TCIABrowser"):
    try:
      self.onReload()
      evalString = 'globals()["%s"].%sTest()' % (moduleName, moduleName)
      tester = eval(evalString)
      tester.runTest()
    except Exception, e:
      import traceback
      traceback.print_exc()
      qt.QMessageBox.warning(slicer.util.mainWindow(),
          "Reload and Test", 'Exception!\n\n' + str(e) + "\n\nSee Python Console for Stack Trace")


#
# TCIABrowserLogic
#

class TCIABrowserLogic:
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget
  """
  def __init__(self):
    pass

  def hasImageData(self,volumeNode):
    """This is a dummy logic method that
    returns true if the passed in volume
    node has valid image data
    """
    if not volumeNode:
      print('no volume node')
      return False
    if volumeNode.GetImageData() == None:
      print('no image data')
      return False
    return True

  def run(self,inputVolume,outputVolume):
    """
    Run the actual algorithm
    """
    return True


class TCIABrowserTest(unittest.TestCase):
  """
  This is the test case for your scripted module.
  """

  def delayDisplay(self,message,msec=1000):
    """This utility method displays a small dialog and waits.
    This does two things: 1) it lets the event loop catch up
    to the state of the test so that rendering and widget updates
    have all taken place before the test continues and 2) it
    shows the user/developer/tester the state of the test
    so that we'll know when it breaks.
    """
    print(message)
    self.info = qt.QDialog()
    self.infoLayout = qt.QVBoxLayout()
    self.info.setLayout(self.infoLayout)
    self.label = qt.QLabel(message,self.info)
    self.infoLayout.addWidget(self.label)
    qt.QTimer.singleShot(msec, self.info.close)
    self.info.exec_()

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_TCIABrowser1()

  def test_TCIABrowser1(self):
    """ Ideally you should have several levels of tests.  At the lowest level
    tests sould exercise the functionality of the logic with different inputs
    (both valid and invalid).  At higher levels your tests should emulate the
    way the user would interact with your code and confirm that it still works
    the way you intended.
    One of the most important features of the tests is that it should alert other
    developers when their changes will have an impact on the behavior of your
    module.  For example, if a developer removes a feature that you depend on,
    your test should break so they know that the feature is needed.
    """

    mainWidget = slicer.modules.pcampreview.widgetRepresentation().self()

    self.delayDisplay("Starting the test here!")
    #
    # first, get some data
    #
    mainWidget.onStep1Selected()
    self.delayDisplay('1')

    mainWidget.onStep2Selected()
    self.delayDisplay('2')

    studyItem = mainWidget.studyTable.widget.item(0,0)
    studyItem.setSelected(1)

    mainWidget.onStep3Selected()
    self.delayDisplay('3')
    seriesItem = mainWidget.seriesTable.widget.item(0,0)
    seriesItem.setCheckState(1)

    mainWidget.onStep4Selected()
    self.delayDisplay('4')


    self.delayDisplay('Test passed!')


class ItemTable(object):

  def __init__(self,parent, headerName, multiSelect=False, width=100):
    self.widget = qt.QTableWidget(parent)
    # self.widget.setMinimumWidth(width)
    self.widget.setColumnCount(12)
    self.widget.setHorizontalHeaderLabels([headerName])
    #self.widget.horizontalHeader().setResizeMode(0, qt.QHeaderView.Stretch)
    #self.widget.horizontalHeader().stretchLastSection = 1
    self.widget.setEditTriggers(qt.QAbstractItemView.NoEditTriggers)
    self.multiSelect = multiSelect
    if self.multiSelect == False:
      self.widget.setSelectionMode(qt.QAbstractItemView.SingleSelection)
    self.width = width
    self.items = []
    self.strings = []

    # self.widget.connect('cellClicked(int,int)',self.onCellClicked())
    #self.loadables = {}
    #self.setLoadables([])

  def onCellClicked(self,row,col):
    print('Cell clicked: '+str(row)+','+str(col))

  def addContentItemRow(self,stringCont,row):
    """Add a row to the loadable table
    """
    colStrs = string.split(stringCont,',')
    col = 0
    for colStr in colStrs:
      # name and check state
      self.strings.append(colStr)
      item = qt.QTableWidgetItem(colStr[1:-1])
      item.setCheckState(0)
      #if not self.multiSelect:
      #  item.setFlags(33)
      #else:
      #  # allow checkboxes interaction
      #  item.setFlags(49)
      self.items.append(item)
      self.widget.setItem(row,col,item)
      col += 1

  def setHeader(self,strings):
    self.widget.setColumnCount(len(strings))
    self.widget.setHorizontalHeaderLabels(strings)
    return

  def setContent(self,strings):
    """Load the table widget with a list
    of volume options (of class DICOMVolume)
    """
    self.widget.clearContents()
    self.widget.setColumnWidth(0,int(self.width))
    self.widget.setRowCount(len(strings))
    # self.items = []
    row = 0

    for s in strings:
      self.addContentItemRow(s,row)
      row += 1
      '''
      uid = string.split(s,',')
      if len(uid)>1:
        uid = uid[0]
        self.addContentItemRow(uid[1:-1],row)
        row += 1
      '''

    self.widget.setVerticalHeaderLabels(row * [""])

  def uncheckAll(self):
    for row in xrange(self.widget.rowCount):
      item = self.widget.item(row,0)
      item.setCheckState(False)

  def checkAll(self):
    for row in xrange(self.widget.rowCount):
      item = self.widget.item(row,0)
      item.setCheckState(True)
      print('Checked: '+str(item.checkState()))

  def getSelectedItem(self):
    for row in xrange(self.widget.rowCount):
      for col in xrange(self.widget.columnCount):
        item = self.widget.item(row,col)
        if item.isSelected():
          return item

  def getCheckedItems(self):
    checkedItems = []
    for row in xrange(self.widget.rowCount):
      item = self.widget.item(row,0)
      if item.checkState():
        checkedItems.append(item)
    return checkedItems


  '''
  def updateCheckstate(self):
    for row in xrange(self.widget.rowCount):
      item = self.widget.item(row,0)
      self.loadables[row].selected = (item.checkState() != 0)
  '''

