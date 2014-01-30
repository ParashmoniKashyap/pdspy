import ctypes
import numpy
import os
import astropy
import h5py

lib = ctypes.cdll.LoadLibrary(os.path.dirname(__file__)+'/libspectroscopy.so')
lib.new_Spectrum.restype = ctypes.c_void_p

class Spectrum:

    def __init__(self, wave=None, flux=None, unc=None):
        if (wave != None):
            self.wave = wave
            self.flux = flux
            if unc == None:
                self.unc = numpy.zeros(wave.size)
            else:
                self.unc = unc

            self.obj = lib.new_Spectrum( \
                    wave.ctypes.data_as(ctypes.POINTER(ctypes.c_double)), \
                    flux.ctypes.data_as(ctypes.POINTER(ctypes.c_double)), \
                    unc.ctypes.data_as(ctypes.POINTER(ctypes.c_double)), \
                    ctypes.c_int(wave.size))

    def __del__(self):
        lib.delete_Spectrum(ctypes.c_void_p(self.obj))

    def asFITS(self):
        hdulist = astropy.io.fits.HDUList([])

        hdu = pyfits.PrimaryHDU(numpy.concatenate(( \
                self.wave.reshape((1,self.wave.size)), \
                self.flux.reshape((1,self.wave.size)), \
                self.unc.reshape((1,self.wave.size)))))
        hdulist.append(hdu)

        return hdulist

    def read(self, filename=None, usefile=None):
        if (usefile == None):
            f = h5py.File(filename, "r")
        else:
            r = usefile

        wave = f['wave'].value
        flux = f['flux'].value
        unc = f['unc'].value

        self.__init__(wave, flux, unc)

        if (usefile == None):
            f.close()

    def write(self, filename=None, usefile=None):
        if (usefile == None):
            f = h5py.File(filename, "w")
        else:
            f = usefile

        if hasattr(self, "wave"):
            wave_dset = f.create_dataset("wave", (self.wave.size,), dtype='f')
            wave_dset[...] = self.wave
            flux_dset = f.create_dataset("flux", (self.flux.size,), dtype='f')
            flux_dset[...] = self.flux
            unc_dset = f.create_dataset("unc", (self.unc.size,), dtype='f')
            unc_dset[...] = self.unc

        if (usefile == None):
            f.close()
