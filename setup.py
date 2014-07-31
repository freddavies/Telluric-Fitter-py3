from distutils.core import setup
from setuptools.command.install import install
from distutils.extension import Extension
import os
import subprocess
import sys

try:
    from Cython.Distutils import build_ext
except ImportError:
    print "You need to install cython before running setup.py"
    print "Run 'pip install cython'"
    print '       or'
    print "'apt-get install cython' (if using a debian-based linux OS)"
    sys.exit()
try:
    import numpy
except ImportError:
    print "You need to install numpy just to run setup.py"
    print "Run 'pip install numpy'"
    print '       or'
    print "'apt-get install python-numpy' (if using a debian-based linux OS)"
    sys.exit()

"""
Below are some default values, which the user may change
"""
# Starting wavelength (in nm) to use for the binary line list
#  TelluricFitter will not be able to generate lines with lower wavelengths!
wavestart = 300


#Ending wavelength (in nm) to use for the binary line list
#  TelluricFitter will not be able to generate lines with higher wavelengths!
waveend = 5000


#The number of running directories for LBLRTM. We need more
#  than one so that we can run multiple instances of 
#  TelluricFitter at once without overwriting input files
num_rundirs = 4


#Ensure a directory exists. Create it if not
def ensure_dir(d):
    if not os.path.exists(d):
        os.makedirs(d)





def GetCompilerString():
    """
    The following function determines what the operating system is,
      and which fortran compiler to use for compiling lnfl and lblrtm.
      It returns the string that the makefiles for lnfl and lblrtm
      need.

      NOTE: This should all work for linux or Mac OSX, but NOT Windows!!
    """
    #First, get the operating system
    p = sys.platform
    if "linux" in p:
        output = "linux"
    elif "darwin" in p:
        output = "osx"
    else:
        raise OSError("Unrecognized operating system: %s" % p)

    #Next, find the fortran compiler to use
    compilers = ["ifort",
                 "gfortran",
                 "g95"]
    comp_strs = ["INTEL",
                 "GNU",
                 "G95"]
    found = False
    for i in range(len(compilers)):
        compiler = compilers[i]
        try:
            subprocess.check_call([compiler, '--help'], stdout=open("/dev/null"))
            found = True
        except OSError:
            found = False
        if found:
            break
    if not found:
        raise OSError("Suitable compiler not found!")
    else:
        output = output + comp_strs[i] + "sgl"
    return output





def MakeTAPE3(directory):
    """
    The following will generate a TAPE3, which is needed for LBLRTM.
     The directory of the lnfl executable must be given.
    """
    #Delete and tape files that are already there
    for fname in ["TAPE1", "TAPE2", "TAPE5", "TAPE6", "TAPE10"]:
        if fname in os.listdir(directory):
            subprocess.check_call(["rm", "%s/%s" % (directory, fname)])


    #Make the parameter file (TAPE5)
    wavenum_start = ("%.3f" % (1e7 / waveend)).rjust(10)
    wavenum_end = ("%.3f" % (1e7 / wavestart)).rjust(10)
    lines = ["$ TAPE5 file for LNFL, generated by setup.py\n", ]
    lines.append("%s%s\n" % (wavenum_start, wavenum_end))
    lines.append("1111111111111111111111111111111111111111")
    outfile = open("%s/TAPE5" % directory, "w")
    outfile.writelines(lines)
    outfile.close()


    #Link the HITRAN line list to the current directory
    linfile = "%s/aer_v_3.2/line_file/aer_v_3.2" % (os.getcwd())
    subprocess.check_call(["ln", "-s", linfile, "%s/TAPE1" % directory])


    #Run LNFL to generate TAPE3
    lnfl_ex = [f for f in os.listdir(directory) if "lnfl" in f][0]
    print "\nUsing LNFL to generate a linelist for use by LBLRTM"
    print "  You may change the wavelength range at the top of "
    print "  the setup.py script. Saving run information in"
    print "        lnfl_run.log"
    print "  This may take a while...\n"
    subprocess.check_call(["./%s" % lnfl_ex, ], stdout=open("lnfl_run.log", "w"), stderr=subprocess.STDOUT,
                          cwd=directory)

    return





def MakeLBLRTM():
    """
    The following is called by build. It does the following things
    1) Unpacks all the lblrtm tar-files
    2) Builds the lblrtm and lnfl executables using their makefiles
        Note: the fortran compiler is determined above
    3) Generates a TAPE3 using LNFL, which LBLRTM needs as a static input
    4) Generates rundirs in the current directory, and populates them
        with the necessary files
    5) Outputs the bash commands that need to be run in order to setup
        the correct environment variables, and offers to append these
        to the user's ~/.bashrc
    """
    #Unpack the tar files
    for fname in ['aer_v_3.2.tar.gz', 'aerlnfl_v2.6.tar.gz', 'aerlbl_v12.2.tar.gz']:
        if fname in os.listdir("./"):
            print "Un-packing %s" % fname
            subprocess.check_call(["tar", "-xzf", fname])
        else:
            print "\n\n*****    Error!   *****"
            print "     %s not found in current directory!\n\n" % fname
            sys.exit()


    #Build the executables
    make_str = GetCompilerString()
    subprocess.check_call(["make", "-f", "make_lnfl", make_str], cwd="./lnfl/build")
    subprocess.check_call(["make", "-f", "make_lblrtm", make_str], cwd="./lblrtm/build")


    #Generate a TAPE3, if necessary.
    if "TAPE3" not in os.listdir("./lnfl"):
        MakeTAPE3("./lnfl")


    #Make run directories with all of the relevant files/scripts/etc.
    for i in range(1, num_rundirs + 1):
        directory = "rundir%i" % i
        print "Making %s" % directory
        ensure_dir(directory)
        ensure_dir("%s/OutputModels" % directory)
        for fname in ["runlblrtm_v3.sh", "MIPAS_atmosphere_profile", "ParameterFile", "TAPE5"]:
            subprocess.check_call(["cp", "data/%s" % fname, "%s/" % directory])

        if "TAPE3" in os.listdir(directory):
            subprocess.check_call(["rm", "%s/TAPE3" % directory])
        subprocess.check_call(["ln", "-s", "%s/lnfl/TAPE3" % (os.getcwd()), "%s/TAPE3" % directory])

        lblrtm_ex = [f for f in os.listdir("./lblrtm") if f.startswith("lblrtm")][0]
        if "lblrtm" in os.listdir(directory):
            subprocess.check_call(["rm", "%s/lblrtm" % directory])
        subprocess.check_call(["ln", "-s", "%s/lblrtm/%s" % (os.getcwd(), lblrtm_ex), "%s/lblrtm" % directory])

        #Make sure the permissions are correct:
        subprocess.check_call(["chmod", "-R", "777", "%s/" % directory])
        #cmd = "chmod 777 %s/*" %directory
        #subprocess.check_call(cmd, shell=True)
        #subprocess.check_call(["chmod", "777", "%s/*" %directory])


    #Finally, we need to set the environment variable TELLURICMODELING.
    line = "export TELLURICMODELING=%s/\n" % os.getcwd()
    print "\nLBLRTM is all set up! The TelluricFitter code requires an environment variable to know where the lblrtm run directories are. You can set the appropriate environment variable with the following command:"
    print "\n\t%s" % line
    inp = raw_input(
        "\nWould you like us to run this command, and append it to your bash profile (~/.bashrc), so that the environment variable will be set every time you open a new terminal? Note: if you ran setup.py as super-user, you should choose no and do it yourself! [Y/n] ")
    if "y" in inp.lower() or inp.strip() == "":
        infile = open("%s/.bashrc" % (os.environ["HOME"]), "a+r")
        lines = infile.readlines()
        if line in lines:
            print "The appropriate environment variable is already set!"
        else:
            infile.write(line)
        infile.close()
        subprocess.check_call(line, shell=True)

    return


"""
The following classes call MakeLBLRTM, and then do the normal
  installation stuff
"""


class CustomInstallCommand(install):
    def run(self):
        MakeLBLRTM()
        install.run(self)


class CustomBuildExtCommand(build_ext):
    def run(self):
        MakeLBLRTM()
        build_ext.run(self)


"""
  This only does the install. Useful if something went wrong
  but LBLRTM already installed
"""


class OnlyInstall(install):
    def run(self):
        install.run(self)


requires = ['matplotlib',
            'numpy>=1.6',
            'scipy>=0.13',
            'astropy>=0.2',
            'lockfile',
            'pysynphot>=0.7',
            'fortranformat']

setup(name='TelFit',
      version='1.0',
      author='Kevin Gullikson',
      author_email='kgulliks@astro.as.utexas.edu',
      url="http://www.as.utexas.edu/~kgulliks/projects.html",
      py_modules=['TelluricFitter',
                  'MakeModel',
                  'DataStructures',
                  'MakeTape5'],
      ext_modules=[Extension("FittingUtilities", ["src/FittingUtilities.pyx"],
                             include_dirs=[numpy.get_include()],
                             extra_compile_args=["-O3", "-funroll-loops"]),
      ],
      cmdclass={'build_ext': CustomBuildExtCommand,
                'FittingUtilities': build_ext,
                'SkipLBL': OnlyInstall},
      data_files=[('', ['data/MIPAS_atmosphere_profile',
                        'data/ParameterFile',
                        'data/TAPE5',
                        'data/runlblrtm_v3.sh']), ],
      install_requires=requires,
      package_dir={'': 'src'}
)


