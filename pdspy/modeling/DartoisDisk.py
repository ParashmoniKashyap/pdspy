import scipy.integrate
import numpy
from ..constants.physics import G, m_p, k, m_p
from ..constants.astronomy import AU, M_sun
from .Disk import Disk

class DartoisDisk(Disk):
    def gas_density(self, x1, x2, x3, coordsys="spherical"):
        ##### Set up the coordinates

        if coordsys == "spherical":
            rt, tt, pp = numpy.meshgrid(x1*AU, x2, x3, indexing='ij')

            rr = rt*numpy.sin(tt)
            zz = rt*numpy.cos(tt)
        elif coordsys == "cartesian":
            xx, yy, zz = numpy.meshgrid(x1*AU, x2*AU, x3*AU, indexing='ij')

            rr = (xx**2 + yy**2)**0.5
        elif coordsys == "cylindrical":
            rr, pp, zz = numpy.meshgrid(x1*AU, x2, x3*AU, indexing='ij')

        # Set up the high resolution grid.

        r = numpy.logspace(numpy.log10(rt.min()), numpy.log10(rt.max()),1000)/AU
        z = numpy.logspace(-2., numpy.log10(rr.max()/AU), 1000)
        phi = numpy.array([0.,2*numpy.pi])

        # Calculate the temperature structure.

        T = self.temperature(r, phi, z, coordsys="cylindrical")[:,0,:]

        # Now make the high resolution coordinates into 3D arrays.

        r, z = numpy.meshgrid(r, z, indexing='ij')

        rho = numpy.sqrt(r**2 + z**2)
        theta = numpy.arctan(r / z)

        # Now calculate the derivative of T.

        dlogT = numpy.gradient(numpy.log(T), z[0,:]*AU, axis=1)

        # Calculate the balance of gravity and pressure

        mu = 2.37
        cs = (k*T/(mu*m_p))**0.5
        M = 1.*M_sun

        gravity = 1./cs**2 * G*M*z*AU / ((r*AU)**2 + (z*AU)**2)**1.5

        # Now vertically integrate to get -logDens.

        logDens = -scipy.integrate.cumtrapz(dlogT+gravity, x=z*AU, initial=0., \
                axis=1)

        # Get the proper normalization.

        norm = 0.5*100*self.surface_density(r[:,0]) / scipy.integrate.trapz(\
                numpy.exp(logDens), x=z*AU, axis=1)

        norm_arr = numpy.zeros(r.shape)
        for i in range(r.shape[1]):
            norm_arr[:,i] = norm

        # Finally, calculate the scaled density.

        logDens += numpy.log(norm_arr)

        # Now, interpolate that density onto the actual grid of interest.

        points = numpy.empty((rho.size, 2))
        points[:,0] = numpy.log10(rho).reshape((-1,))
        points[:,1] = theta.reshape((-1,))

        logDens_interp = scipy.interpolate.griddata(points, logDens.reshape((\
                -1,)), (numpy.log10(rt/AU), tt))

        Dens = numpy.exp(logDens_interp)

        return Dens

    def number_density(self, r, theta, phi, gas=0):
        rho_gas = self.gas_density(r, theta, phi)

        rho_gas_critical = (100. / 0.8) * 2.37*m_p
        rho_gas[rho_gas < rho_gas_critical] = 1.0e-50

        n_H2 = rho_gas * 0.8 / (2.37*m_p)

        n = n_H2 * self.abundance[gas]

        # Account for freezeout as well.

        T = self.temperature(r, theta, phi, coordsys="spherical")

        n[T < self.freezeout[gas]] *= 1.0e-8

        return n

    def temperature(self, x1, x2, x3, coordsys="spherical"):
        ##### Disk Parameters
        
        rin = self.rmin * AU
        rout = self.rmax * AU
        pltgas = self.pltgas
        tmid0 = self.tmid0
        tatm0 = self.tatm0
        zq0 = self.zq0 * AU
        delta = self.delta

        ##### Set up the coordinates

        if coordsys == "spherical":
            rt, tt, pp = numpy.meshgrid(x1*AU, x2, x3, indexing='ij')

            rr = rt*numpy.sin(tt)
            zz = rt*numpy.cos(tt)
        elif coordsys == "cartesian":
            xx, yy, zz = numpy.meshgrid(x1*AU, x2*AU, x3*AU, indexing='ij')

            rr = (xx**2 + yy**2)**0.5
        elif coordsys == "cylindrical":
            rr, pp, zz = numpy.meshgrid(x1*AU, x2, x3*AU, indexing='ij')

        ##### Make the dust density model for a protoplanetary disk.
        
        zq = zq0 * (rr / (1*AU))**1.3

        tmid = tmid0 * (rr / (1*AU))**(-pltgas)
        tatm = tatm0 * (rr / (1*AU))**(-pltgas)

        t = numpy.zeros(tatm.shape)
        t[zz >= zq] = tatm[zz >= zq]
        t[zz < zq] = tatm[zz < zq] + (tmid[zz < zq] - tatm[zz < zq]) * \
                (numpy.cos(numpy.pi * zz[zz < zq] / (2*zq[zz < zq])))**(2*delta)
        
        return t

    def microturbulence(self, r, theta, phi):
        ##### Disk Parameters
        
        rin = self.rmin * AU
        rout = self.rmax * AU
        t0 = self.t0
        plt = self.plt

        ##### Set up the coordinates

        rt, tt, pp = numpy.meshgrid(r*AU, theta, phi,indexing='ij')

        rr = rt*numpy.sin(tt)
        zz = rt*numpy.cos(tt)

        ##### Make the dust density model for a protoplanetary disk.
        
        aturb = numpy.ones(rr.shape)*self.aturb*1.0e5
        
        return aturb

    def velocity(self, r, theta, phi, mstar=0.5):
        mstar *= M_sun

        rt, tt, pp = numpy.meshgrid(r*AU, theta, phi,indexing='ij')

        rr = rt*numpy.sin(tt)
        zz = rt*numpy.cos(tt)

        v_r = numpy.zeros(rr.shape)
        v_theta = numpy.zeros(rr.shape)
        v_phi = numpy.sqrt(G*mstar*rr**2/rt**3)

        return numpy.array((v_r, v_theta, v_phi))
