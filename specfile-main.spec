# -*- mode: python -*-

block_cipher = None


a = Analysis(['main.py'],
             pathex=['Z:\\home\\kangalioo\\dev\\python\\etterna-graph-2'],
             binaries=[],
             datas=[],
             hiddenimports=[#'scipy',
                            # ~ 'scipy.special._ufuncs_cxx',
                            # ~ 'scipy.linalg.cython_blas',
                            # ~ 'scipy.linalg.cython_lapack',
                            # ~ 'scipy.integrate',
                            # ~ 'scipy.integrate.quadrature',
                            # ~ 'scipy.integrate.odepack',
                            # ~ 'scipy.integrate._odepack',
                            # ~ 'scipy.integrate.quadpack',
                            # ~ 'scipy.integrate._quadpack',
                            # ~ 'scipy.integrate._ode',
                            # ~ 'scipy.integrate.vode',
                            # ~ 'scipy.integrate._dop',
                            # ~ 'scipy.integrate.lsoda'
                            ],
             hookspath=[],
             runtime_hooks=[],
             excludes=["matplotlib", "tk", "tcl", "mpl-data", "PySide2"],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

##### include mydir in distribution #######
def extra_datas(mydir):
    def rec_glob(p, files):
        import os
        import glob
        for d in glob.glob(p):
            if os.path.isfile(d):
                files.append(d)
            rec_glob("%s/*" % d, files)
    files = []
    rec_glob("%s/*" % mydir, files)
    extra_datas = []
    for f in files:
        extra_datas.append((f, f, 'DATA'))

    return extra_datas
###########################################

# append the 'data' dir
# a.datas += extra_datas('pyqtgraph_git')

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='main',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=True,
          icon="stuff/icon.ico")
