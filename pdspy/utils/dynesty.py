import pdspy.modeling as modeling
import dynesty.plotting as dyplot
import matplotlib.pyplot as plt
import scipy.stats
import scipy.integrate
import pickle
import numpy

# Define a likelihood function.

def lnlike(p, visibilities, parameters, plot, ncpus=1, source="ObjName", \
        nice=19):

    # Set up the params dictionary.

    keys = []
    for key in sorted(parameters.keys()):
        if not parameters[key]["fixed"]:
            keys.append(key)

    params = dict(zip(keys, p))

    # Run the model.

    m = modeling.run_flared_model(visibilities, params, parameters, plot, \
            ncpus=ncpus, source=source, nice=nice)

    # A list to put all of the chisq into.

    chisq = []

    # Calculate the chisq for the visibilities.

    for j in range(len(visibilities["file"])):
        chisq.append(-0.5*(numpy.sum((visibilities["data"][j].real - \
                m.visibilities[visibilities["lam"][j]].real)**2 * \
                visibilities["data"][j].weights)) + \
                -0.5*(numpy.sum((visibilities["data"][j].imag - \
                m.visibilities[visibilities["lam"][j]].imag)**2 * \
                visibilities["data"][j].weights)))

    # Return the sum of the chisq.

    return numpy.array(chisq).sum()

# Define a prior function.

def ptform(u, parameters, priors):

    # Set up the params dictionary.

    keys = []
    for key in sorted(parameters.keys()):
        if not parameters[key]["fixed"]:
            keys.append(key)

    uparams = dict(zip(keys, u))
    pparams = dict(zip(keys, [0 for i in range(len(u))]))

    # Get the correct order for setting parameters (as some depend on others

    ordered_keys, index = numpy.unique(["logR_env","logR_disk","logR_in", \
            "logTmid0"]+list(parameters.keys()), return_index=True)
    ordered_keys = ordered_keys[numpy.argsort(index)]

    # Now loop through the parameters and transform the ones that aren't fixed.

    for key in ordered_keys:
        if not parameters[key]["fixed"]:
            # R_disk has to be smaller than R_env.
            if key == "logR_disk":
                if "logR_env" in pparams:
                    logR_env = pparams["logR_env"]
                else:
                    logR_env = parameters["logR_env"]["value"]

                pparams[key] = uparams[key] * (min(logR_env, \
                        parameters[key]["limits"][1]) - \
                        parameters[key]["limits"][0]) + \
                        parameters[key]["limits"][0]
            # R_in has to be smaller than R_disk.
            elif key == "logR_in":
                if "logR_disk" in pparams:
                    logR_disk = pparams["logR_disk"]
                else:
                    logR_disk = parameters["logR_disk"]["value"]

                pparams[key] = uparams[key] * (min(logR_disk, \
                        parameters[key]["limits"][1]) - \
                        parameters[key]["limits"][0]) + \
                        parameters[key]["limits"][0]
            # R_cav should be between R_in and R_disk.
            elif key == "logR_cav":
                if "logR_disk" in pparams:
                    logR_disk = pparams["logR_disk"]
                else:
                    logR_disk = parameters["logR_disk"]["value"]

                if "logR_in" in pparams:
                    logR_in = pparams["logR_in"]
                else:
                    logR_in = parameters["logR_in"]["value"]


                pparams[key] = uparams[key] * (min(pparams["logR_disk"], \
                        parameters[key]["limits"][1]) - \
                        max(pparams["logR_in"],parameters[key]["limits"][0])) +\
                        max(pparams["logR_in"],parameters[key]["limits"][0])
            # Tmid0 should be less than Tatm0.
            elif key == "logTmid0":
                pparams[key] = uparams[key] * (min(pparams["logTatm0"], \
                        parameters[key]["limits"][1]) - \
                        parameters[key]["limits"][0]) + \
                        parameters[key]["limits"][0]
            # Make the position angle cyclic.
            elif key == "pa":
                pparams[key] = (uparams[key] % 1.) * 360.
            # If we have a prior on the parallax, use that to get dpc.
            elif key == "dpc" and "parallax" in priors:
                m = priors["parallax"]["value"]
                s = priors["parallax"]["sigma"]
                low = 1. / parameters["dpc"]["limits"][1] * 1000
                high = 1. / parameters["dpc"]["limits"][0] * 1000
                low_n, high_n = (low - m) /s, (high - m) /s

                parallax = scipy.stats.truncnorm.ppf(uparams[key], low_n, \
                        high_n, loc=m, scale=s)

                pparams[key] = 1./parallax * 1000
            # If we have a prior on the stellar mass from the IMF.
            elif key == "logM_star" and "Mstar" in priors:
                imf = imf_gen(a=10.**parameters[key]["limits"][0], \
                        b=10.**parameters[key]["limits"][1])

                pparams[key] = numpy.log10(imf.ppf(uparams[key]))
            # If we have a prior on a parameter, draw the parameter from a 
            # normal distribution.
            elif key in priors:
                m = priors[key]["value"]
                s = priors[key]["sigma"]
                low = parameters[key]["limits"][0]
                high = parameters[key]["limits"][1]
                low_n, high_n = (low - m) /s, (high - m) /s

                pparams[key] = scipy.stats.truncnorm.ppf(uparams[key], low_n, \
                        high_n, loc=m, scale=s)
            # If none of the above apply, then draw from a uniform prior between
            # the provided limits.
            else:
                pparams[key] = uparams[key] * (parameters[key]["limits"][1] - \
                        parameters[key]["limits"][0]) + \
                        parameters[key]["limits"][0]

    # Now get the list of parameter values and return.

    p = [pparams[key] for key in sorted(keys)]

    return p

# Define a few useful classes for generating samples from the IMF.

def chabrier_imf(Mstar):
    if Mstar <= 1.:
        return 0.158 * 1./(numpy.log(10.) * Mstar) * \
                numpy.exp(-(numpy.log10(Mstar)-numpy.log10(0.08))**2/ \
                (2*0.69**2))
    else:
        return 4.43e-2 * Mstar**-1.3 * 1./(numpy.log(10.) * Mstar)

class imf_gen(scipy.stats.rv_continuous):
    def __init__(self, a=None, b=None):
        self.norm = scipy.integrate.quad(chabrier_imf, a, b)[0]

        super().__init__(a=a, b=b)

    def _pdf(self, x):
        return chabrier_imf(x) / self.norm

# Functions for saving the state of the Dynesty Sampler and loading a saved 
# state.

def save_sampler(name, sampler, pool=None, dynamic=False):

    # Clear the random state, as it cannot be pickled.
    sampler.rstate = None

    # Clear the MPI pool, as it also cannot be pickled.
    sampler.pool = None
    sampler.M = map

    # If this is a DynamicNestedSampler object, also do the sub-sampler.
    if dynamic:
        sampler.sampler.rstate = None
        sampler.sampler.pool = None
        sampler.sampler.M = map

    # Save
    pickle.dump(sampler, open(name, "wb"))

    # Restore everything to the way it was before.
    sampler.rstate = numpy.random
    sampler.pool = pool
    if pool != None:
        sampler.M = pool.map
    else:
        sampler.M = map

    # Again, repeat for the sub-sampler, if DynamicNestedSampler.

    if dynamic:
        sampler.sampler.rstate = numpy.random
        sampler.sampler.pool = pool
        if pool != None:
            sampler.sampler.M = pool.map
        else:
            sampler.sampler.M = map

def load_sampler(name, pool=None, dynamic=False):
    # Load the sampler from the pickle file.
    sampler = pickle.load(open("sampler.p","rb"))

    # Add back in the random state.
    sampler.rstate = numpy.random

    # Add the pool correctly.
    sampler.pool = pool
    if pool != None:
        sampler.M = pool.map
        sampler.queue_size = pool.size
        sampler.sampler.M = pool.map
        sampler.sampler.queue_size = pool.size
    else:
        sampler.M = map
        sampler.sampler.M = map

    # Add pool/random state correctly for the sub-sampler as well for 
    # the DynamicNestedSampler class.
    if dynamic:
        sampler.sampler.rstate = numpy.random
        sampler.sampler.pool = pool
        if pool != None:
            sampler.sampler.M = pool.map
            sampler.sampler.queue_size = pool.size
        else:
            sampler.sampler.M = map

    return sampler

# A function to make useful plots as the sampling is running.

def plot_status(res, labels=None, periodic=None):
    # Generate a plot of the trace.

    try:
        fig, ax = dyplot.traceplot(res, show_titles=True, trace_cmap="viridis",\
                connect=True, connect_highlight=range(5), labels=labels)
    except:
        # If it hasn't converged enough...
        fig, ax = dyplot.traceplot(res, show_titles=True, trace_cmap="viridis",\
                connect=True, connect_highlight=range(5), labels=labels, \
                kde=False)

    fig.savefig("traceplot.png")

    plt.close(fig)

    # Generate a bounds cornerplot.

    fig, ax = dyplot.cornerbound(res, it=res.niter-1, periodic=periodic, \
            prior_transform=sampler.prior_transform, show_live=True, \
            labels=labels)

    fig.savefig("boundplot.png")

    plt.close(fig)
