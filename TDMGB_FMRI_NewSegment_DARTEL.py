from os.path import join as opj
from nipype.interfaces import spm
from nipype.interfaces.spm import NewSegment, DARTEL
from nipype.interfaces.utility import Function, IdentityInterface
from nipype.interfaces.io import SelectFiles, DataSink
from nipype.pipeline.engine import Workflow, Node, MapNode, JoinNode  # the workflow and node wrappers
import nipype.interfaces.io as nio
import nipype.interfaces.utility as niu
import os
import time

# Start timing
start = time.time()

# Set the way matlab should be called
import nipype.interfaces.matlab as mlab      # how to run matlab
mlab.MatlabCommand.set_default_matlab_cmd("matlab -nodesktop -nosplash")

# Specify location of data.
dataDir = os.path.abspath('/scr/archimedes1/Glad/Projects/Top-down_mod_MGB/Experiments/TdMGB_fMRI/DATA/sourcedata/')
outDir = os.path.abspath('/scr/archimedes1/Glad/Projects/Top-down_mod_MGB/Experiments/TdMGB_fMRI/DATA/derivatives/')
# BIDS subdirectories
subDirFunc = '/ses-spespk/func'
subDirAnat = '/ses-spespk/anat'
subDirFmap = '/ses-spespk/fmap'
# Specify subject directories.
subs = [
    "sub-01",
    "sub-02",
    "sub-03",
    "sub-04",
    "sub-05",
    "sub-06",
    "sub-08",
    "sub-09",
    "sub-10",
    "sub-11",
    "sub-12",
    "sub-13",
    "sub-14",
    "sub-15",
    "sub-16",
    "sub-18",
    "sub-19",
    "sub-20",
    "sub-21",
    "sub-22",
    "sub-24",
    "sub-26",
    "sub-28",
    "sub-29",
    "sub-30",
    "sub-31",
    "sub-32",
    "sub-33"
]

# Template for datagrabber
field_template = dict(struct='%s%s/%s_acq-T1w.nii')
template_args = dict(struct=[['subject_id', subDirAnat, 'subject_id']])
# Need an identitiy interface to iterate over subject_id and run
infosource = Node(interface=IdentityInterface(fields=['subject_id']),
                     name="infosource")
infosource.iterables = [('subject_id', subs)]

#Grab data
datasource = Node(interface=nio.DataGrabber(infields=['subject_id'],
                                            outfields=['struct']),
                  name='datasource')
datasource.inputs.base_directory = dataDir
datasource.inputs.template = '*'
datasource.inputs.field_template = field_template
datasource.inputs.template_args = template_args
datasource.inputs.subject_id = subs
datasource.inputs.sort_filelist = False

# Specify workflow name.
strucProc = Workflow(name='strucProc', base_dir=outDir+'/tmp')
strucProc.connect([
    (infosource, datasource, [('subject_id', 'subject_id')])
])

# New Segment
segment = MapNode(interface=NewSegment(),
                  iterfield=['channel_files'],
                   name="segment")
segment.inputs.channel_info = (0.0001, 60, (True, True))
segment.inputs.write_deformation_fields = [False, False]  # inverse and forward defomration fields
tpmPath = '/afs/cbs.mpg.de/software/spm/12.6685/9.0/precise/tpm/'
# The "True" statement tells NewSegment to create DARTEL output for:
tissue1 = ((tpmPath+'TPM.nii', 1), 2, (False, True), (False, False))  # grey matter
tissue2 = ((tpmPath+'TPM.nii', 2), 2, (False, True), (False, False))  # white matter
tissue3 = ((tpmPath+'TPM.nii', 3), 2, (False, False), (False, False))
tissue4 = ((tpmPath+'TPM.nii', 4), 2, (False, False), (False, False))
tissue5 = ((tpmPath+'TPM.nii', 5), 2, (False, False), (False, False))
tissue6 = ((tpmPath+'TPM.nii', 6), 2, (False, False), (False, False))
segment.inputs.tissues = [tissue1, tissue2, tissue3, tissue4, tissue5, tissue6]  # Need these for DARTEL output.

strucProc.connect([
    (datasource, segment, [('struct', 'channel_files')])
])

# This was taken from the Dartel Template creation workflow
# http://github.com/nipy/nipype/tree/55d052b/nipype/workflows/fmri/spm/preprocess.py#L228
# Function to get grey and white matter tissue classes from NewSegment.
def get2classes(dartel_files):
    print dartel_files
    class1images = []
    class2images = []
    for session in dartel_files:
        class1images.extend(session[0])
        class2images.extend(session[1])
    return [class1images, class2images]

# DARTEL create template.
dartel = Node(DARTEL(), name="dartel")
# Here I've quadrupled the reg par mu.
# See Ripolles et al., NeuroImage, 2012.
dartel.inputs.iteration_parameters = [ (3, (16,2,1e-06), 1, 16), # inner iter, reg par, time points (K), smoothing
                                       (3, (8, 1,1e-06), 1, 8),
                                       (3, (4, 0.5,1e-06), 2, 4),
                                       (3, (2, 0.25,1e-06), 4, 2),
                                       (3, (1, 0.125,1e-06), 16, 1),
                                       (3, (1, 0.125,1e-06), 64, 0.5) ]

strucProc.connect([
    (segment, dartel, [(('dartel_input_images', get2classes), 'image_files')])
])

# Datasink
sinker = Node(DataSink(base_directory=outDir), name='sinker')
strucProc.connect(infosource, 'subject_id', sinker, 'container') # Define container for sinker, i.e. subject names.
strucProc.connect([
    (segment, sinker, [('dartel_input_images', 'segment')]),
    (dartel, sinker, [('dartel_flow_fields', 'dartel.@flowfields')]),
    (dartel, sinker, [('final_template_file', 'dartel.@template')])
])

# strucProc.write_graph(dotfilename='structural_preprocessing.dot', graph2use='colored', format='pdf')  #, simple_form=True
strucProc.run()  # Add  plugin='MultiProc' in () if you so desire.

# Time again and spit out difference.
print 'Total time: ', ((time.time() - start) / 60), 'mins'
