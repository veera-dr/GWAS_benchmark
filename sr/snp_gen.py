import sys
import os
import numpy as np
import scipy as sp
import logging
import pysnptools.util as pstutil
from pysnptools.snpreader import SnpData

def snp_gen(fst, dfr, iid_count, sid_count, maf_low=.05, maf_high=.5, seed=0,sibs_per_family=10,freq_pop_1=.5): #!!!cmk move this to the front
    """
    #!!!cmk fill in with docs including example

    fst is Degree of Population Structure, e.g. [0.005, 0.01, 0.05, 0.1] !!!cmk was self.FSTs
        fst=0 is a special case #!!!is it?
    dfr is Degree of Family Relatedness, the fraction of individuals belonging to a family [0.0, 0.5, 0.6, 0.7, 0.8, 0.9], e.g. #!!!cmk was self.fracSibs
    iid_count !!!cmk was numIndividuals
    sid_count == numSnps
    MAF is Minor allele frequency
    freq_pop_1 !!cmk was caseFrac ????

    #!!!cmk do we still want maf_high?
    #!!!cmk, freq_pop_1=.5, 


    """
    snps = _generate_data(num_snps=sid_count,randomseed=seed,fracSibs=dfr,numIndividuals=iid_count,num_children=sibs_per_family,pop_perc=freq_pop_1,maf_low=maf_low,maf_high=maf_high,fst=fst)

    iid, sid, pos =  _write_plink(snps)

    snpdata = SnpData(iid, sid, pos, snps, 
                      parent_string="snp_gen(fst={0}, dfr={1}, iid_count={2}, sid_count={3}, maf_low={4})".format(fst, dfr, iid_count, sid_count, maf_low) #!!!cmk is this up-to-date?
                      )

    return snpdata

class _sim_snps(object):
    """
    Generates genotypes with a certain MAF and optionally with population structure.
    In case of no population structure, they are sampled from a binomial,
    otherwise from a Beta-Binomial (Balding and Nichols, 1995).
    """
    def __init__(self, num_snps, num_differentiated = np.array([0]), MAF_ancestral = np.array([0.05,0.5]), Fst = np.array([[0.1,0.1]]), diploid = True, p_ancestral=None):
        self.differentiated = None
        self.num_snps=num_snps
        self.MAF_ancestral = MAF_ancestral
        self.Fst = Fst                                  #dimensions: number populations times number SNP groups
        self.num_differentiated = num_differentiated    #dimensions: number of SNP groups
        self.p_ancestral=p_ancestral

        #set differentiated SNPs
        i_0 = 0
        self.differentiated = np.zeros((len(self.num_differentiated),self.num_snps),dtype = 'bool')
        
        for i_group, num_diff in enumerate(self.num_differentiated):
            self.differentiated[i_group,np.arange(i_0,i_0+num_diff)]=True
            i_0+=num_diff
        
        if diploid:
            self.chr_copies = 2
        else:
            self.chr_copies = 1

        #set the allele frequencies
        self.sample_frequencies()



    def sample_frequencies(self):
        '''
        sample the allele frequencies for all ancestral SNPs and all populations
        ancestral frequencies are sampled uniformly according to MAFs
        population frequencies from a Beta distribution (Balding and Nichols, 1995).
        '''
        #sample ancestral allele frequencies, len(p)=num_snps
        if self.p_ancestral is None:
            self.p_ancestral = np.random.uniform(self.MAF_ancestral[0], self.MAF_ancestral[1], self.num_snps)
        
        #alphas: shape number(populations) times number(snps) and copy over ancestral frequencies
        self.alphas = np.zeros((len(self.Fst[0]),self.p_ancestral.shape[0]))
        self.alphas[:,:]=self.p_ancestral
        
        #re-sample differentiated population frequencies
        for i_snpgroup in xrange(len(self.num_differentiated)):
            for i_population, F in enumerate(self.Fst[i_snpgroup]):
                i_snps = self.differentiated[i_snpgroup]
                p_anc = self.p_ancestral[i_snps]
                if F == 0.0: 
                    self.alphas[i_population,i_snps] = p_anc #special treatment if no population structure
                else:
                    self.alphas[i_population,i_snps] = np.random.beta(p_anc*(1.0-F)/F,(1.0-p_anc)*(1.0-F)/F, p_anc.shape[0])
        pass


    def mate(self, snps_parents, i_parent, num_children_per_couple):
        '''
        given a set of snps for the parents, mate the individuals
        '''
        assert self.chr_copies==2, "assert self.chr_copies==2"
        num_snps = snps_parents[0].shape[1]
        num_trios = i_parent.shape[0]
        num_children = num_trios*num_children_per_couple #10 children per couple
        snps = np.zeros((num_children,num_snps),dtype='int8')
        
        for i in xrange(len(snps_parents)):
            #sample each allele
            for j in xrange(num_children_per_couple):
                rand = np.random.random((num_trios,num_snps))
                snps[j*num_trios:(j+1)*num_trios][rand<0.5*snps_parents[i]]+=1
        return snps

    def generate_trios(self, snps_parents=None, num_trios=0, population_percentages=None, snp_index=None, num_children_per_couple=1):
        '''
        generate a single set of trios
        '''    
        assert self.chr_copies==2, "assert self.chr_copies==2"
        num_trios = int(num_trios)
        if snps_parents is None:
            #sample parents
            sample_size = 2*num_trios
            snps_parents = self.generate_snps_populations(sample_size=sample_size,population_percentages=population_percentages,snp_index=snp_index)
        else:
            sample_size = snps_parents.shape[0]
        num_snps = snps_parents.shape[1]
        assert sample_size>=2*num_trios, "sample_size>=2*num_trios"
        potential_parents = np.random.permutation(sample_size)
        i_done=0
        i_parent = np.empty([num_trios,self.chr_copies],dtype = 'int64')
        snps_parents_sampled = []
        for i in xrange(self.chr_copies):
            #sample each allele
            i_parent[:,i] = potential_parents[i_done:i_done+num_trios]
            snps_parents_sampled.append(snps_parents[i_parent[:,i]])
            i_done+=num_trios
        snps = self.mate(snps_parents_sampled, i_parent, num_children_per_couple)
        return snps, i_parent

    def generate_snps(self, sample_size, snps=None, population_index=None, snp_index = None):
        """
        Generates genotypes with a certain MAF and optionally with population structure.
        In case of no population structure, they are sampled from a binomial,
        otherwise from a Beta-Binomial (Balding and Nichols, 1995).
        """
        if snp_index is None:
            snp_index = np.arange(self.num_snps)
        if population_index is None:
            logging.info("Simulating SNPs from ancestral frequencies...")
            #generate from ancestral frequencies
            pgen = self.p_ancestral[snp_index]
        else:        
            logging.info("Simulating SNPs from population %i" % population_index)

            #generate from population frequencies    
            pgen = self.alphas[population_index,snp_index]
        if snps is None:
            snps = np.zeros((sample_size,pgen.shape[0]),dtype='int8')
        else:
            snps[:]=0
        for i in xrange(self.chr_copies):
            #sample each allele
            rand = np.random.random((sample_size,pgen.shape[0]))
            snps[rand<pgen]+=1
        #snps_ = np.random.binomial(self.chr_copies,pgen,(sample_size,pgen.shape[0]))
        return snps

def _generate_data(num_snps, randomseed,fracSibs,numIndividuals,num_children,pop_perc,maf_low,maf_high,fst):
    
    #set random seed
    np.random.seed(randomseed)

    num_trios = int(numIndividuals*fracSibs/(2 * num_children)) #!!trio is a misnomer because mom+dad+10 kids
    num_samples = numIndividuals-numIndividuals*fracSibs
    num_differentiated = np.array([num_snps])
    Fst = np.array([[fst,fst]])
    
    assert 0 <= pop_perc and pop_perc <=1.0,"assert 0 <= pop_perc and pop_perc <=1.0"
    pop_perc = np.array([pop_perc, 1.0-pop_perc])
    

    num_trios_pop= pop_perc*num_trios
    simsnps = _sim_snps(num_snps, num_differentiated = num_differentiated, MAF_ancestral = np.array([maf_low,maf_high]), Fst = Fst, p_ancestral=None)

    snps_pop=[]
    i_parent_pop=[]
    nonchild_index_list = []
    nonchild_start = 0
    for i_pop in xrange(len(pop_perc)):
        snps=simsnps.generate_snps(int(num_samples*pop_perc[i_pop]),population_index = i_pop, snp_index = None)
        nonchild_index_list = nonchild_index_list + range(nonchild_start,nonchild_start+len(snps))
        snps_kids,i_parent = simsnps.generate_trios(snps_parents=snps, num_trios=num_trios_pop[i_pop], population_percentages=None, snp_index=None, num_children_per_couple=num_children)
        nonchild_start += len(snps) + len(snps_kids)
        snps_pop.append(np.concatenate([snps,snps_kids],0))
        i_parent_pop.append(i_parent)
    snps_all = np.concatenate(snps_pop,0)
    
    snps_kids,i_parent = simsnps.generate_trios(snps_parents=snps_all, num_trios=num_trios, population_percentages=None, snp_index=None, num_children_per_couple=num_children)
    snps_all = np.concatenate([snps_all,snps_kids],0)
    return snps_all

def _write_plink(X): #!!!cmk rename
    #import plink_write as pw
    sample_names =  np.array(['i_%d' % i for i in range(X.shape[0])], dtype=str)
    family_names = np.array(['f_%d' % i for i in range(X.shape[0])], dtype=str)[:, None]
    paternal_ids = np.zeros_like(family_names,dtype=str)
    maternal_ids = np.zeros_like(family_names,dtype=str)
    sex = np.zeros_like(family_names,dtype=str)
    fam_pid_mid_sex = np.concatenate((family_names, paternal_ids, maternal_ids, sex), axis=1)
    sid=np.empty(X.shape[1],dtype='|S15')
    for i in range(X.shape[1]):
        sid[i] = 'snp_%d' %i

    iid = np.array(list(zip(sample_names,family_names[:,0])))
    pos = np.array(list([i,0,0] for i in xrange(len(sid)))) # every snp has position 0,0 on its own chrom

    return iid, sid, pos

if __name__ == "__main__":

    logging.basicConfig(level=logging.INFO)

    snpdata = snp_gen(fst=.1,dfr=.1,iid_count=100,sid_count=1000)
    print snpdata


    import doctest
    doctest.testmod()


    print "done"

