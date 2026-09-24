---
id: 2020_antaki_kahwati
title: "Predictive modeling of proliferative vitreoretinopathy using automated machine learning by ophthalmologists without coding experience"
authors: ["Fares Antaki", "Ghofril Kahwati"]
year: 2020
venue: "Scientific Reports"
source: pubmed
url: https://pubmed.ncbi.nlm.nih.gov/33177614/
doi: 10.1038/s41598-020-76665-3
arxiv_id:
pmid: "33177614"
pmcid: PMC7658348
paywalled:
full_text: full
full_text_source: europepmc-xml
extraction_warning:
---

# Predictive modeling of proliferative vitreoretinopathy using automated machine learning by ophthalmologists without coding experience

## Abstract

We aimed to assess the feasibility of machine learning (ML) algorithm design to predict proliferative vitreoretinopathy (PVR) by ophthalmologists without coding experience using automated ML (AutoML). The study was a retrospective cohort study of 506 eyes who underwent pars plana vitrectomy for rhegmatogenous retinal detachment (RRD) by a single surgeon at a tertiary-care hospital between 2012 and 2019. Two ophthalmologists without coding experience used an interactive application in MATLAB to build and evaluate ML algorithms for the prediction of postoperative PVR using clinical data from the electronic health records. The clinical features associated with postoperative PVR were determined by univariate feature selection. The area under the curve (AUC) for predicting postoperative PVR was better for models that included pre-existing PVR as an input. The quadratic support vector machine (SVM) model built using all selected clinical features had an AUC of 0.90, a sensitivity of 63.0%, and a specificity of 97.8%. An optimized Naïve Bayes algorithm that did not include pre-existing PVR as an input feature had an AUC of 0.81, a sensitivity of 54.3%, and a specificity of 92.4%. In conclusion, the development of ML models for the prediction of PVR by ophthalmologists without coding experience is feasible. Input from a data scientist might still be needed to tackle class imbalance—a common challenge in ML classification using real-world clinical data.

Subject terms: Predictive markers, Risk factors, Outcomes research

## Introduction

Despite advances in retinal detachment surgery, proliferative vitreoretinopathy (PVR) remains an important barrier for long-term successful anatomic repair of a rhegmatogenous retinal detachment (RRD)^(1,2). PVR has a cumulative risk of 5–10% of all retinal detachment repairs and is responsible for 75% of all primary surgical failures^1. Several clinical and biological risk factors have been identified in the past two decades for PVR formation including trauma, aphakia, vitreous hemorrhage, and pre-existing PVR^(3–9).

Multiple formulas have been developed to predict PVR based on genetic and clinical variables but their poor predictive performance made them unsuitable for routine clinical use^(10–13). Ideal predictive formulas should identify high-risk cases in order to guide future clinical management^(14). While artificial intelligence (AI) solutions have been broadly applied to imaging data in ophthalmology, a limited number of studies have utilized AI techniques with clinical data obtained from electronic health records (EHRs)^(15). In the case of PVR, part of the difficulty of building predictive models using clinical data lies in the low incidence of the disease within the clinical cohorts, leading to imbalanced datasets^(15,16).

As of recently, the development of machine learning (ML) predictive models in healthcare had been reserved for AI experts with knowledge of coding and computer science. The feasibility of deep-learning design (a subset of AI) by physicians without coding experience was demonstrated in a first-of-its-kind report by Faes et al. in 2019^(17). This major advance in the democratization of AI was made possible by the release of automated ML (AutoML) programs by major companies allowing any individual to develop high-quality AI models^(18).

In this study, two ophthalmologists without coding experience built ML predictive classification models using an interactive application in MATLAB (MathWorks, Natick, MA) and explored the discriminative performance of those models for the prediction of postoperative PVR. To our knowledge, this is the first study examining the feasibility of AutoML prediction of postoperative complications of vitreoretinal surgery.

## Results

### Discriminative performance of the machine learning models

Table 3 provides a summary of the discriminative performance of all 4 ML models. The receiver operating characteristics curves (ROC) are presented in Fig. 2. The best-performing model was the quadratic SVM that included all relevant clinical variables (Model 1). The AUC was 0.90. The computed sensitivity and specificity were 63.0% and 97.8%, respectively. The PPV and NPV were 93.5% (adjusted 74.4%) and 84.1% (adjusted 96.4%) respectively. Model 2 had an AUC of 0.86, higher sensitivity (69.6%), lower specificity (95.7%), lower PPV (88.9%, adjusted 61.6%), and higher NPV (86.3%, adjusted 96.9%). Models that did not include pre-existing PVR as an input (Feature Set 2) had lower diagnostic properties. Model 3 had an AUC of 0.81. The sensitivity and specificity were 45.7% and 94.6%, respectively. The PPV and NPV were 80.8% (adjusted 45.7%) and 77.7% (adjusted 94.6%), respectively. Model 4 had an AUC of 0.81, a sensitivity of 54.3%, and a specificity of 92.4%. The PPV and NPV were 78.1% (adjusted 41.7%) and 80.2% (adjusted 95.3%), respectively.

**Table 3 Summary of the discriminative performance of all 4 ML models.**

| Model | TP | FP | TN | FN | AUC | F1 | SN (%) | SP (%) | PPV (%) | NPV (%) |
|---|---|---|---|---|---|---|---|---|---|---|
| Feature Set 1 (8 features) |  |  |  |  |  |  |  |  |  |  |
| Model 1: Quadratic SVM | 29 | 2 | 90 | 17 | 0.90 | 0.75 | 63.0 | 97.8 | 93.5 | 84.1 |
| Model 2: Optimized NB | 32 | 4 | 88 | 14 | 0.86 | 0.78 | 69.6 | 95.7 | 88.9 | 86.3 |
| Feature Set 2 (7 features) |  |  |  |  |  |  |  |  |  |  |
| Model 3: Optimized SVM | 21 | 5 | 87 | 25 | 0.81 | 0.58 | 45.7 | 94.6 | 80.8 | 77.7 |
| Model 4: Optimized NB | 25 | 7 | 85 | 21 | 0.81 | 0.64 | 54.3 | 92.4 | 78.1 | 80.2 |

ML machine learning, TP true positives, FP false positives, TN true negatives, FN false negatives, AUC area under the receiver operating characteristics, F1 F1 score, SN sensitivity, SP specificity, PPV positive predictive value, NPV negative predictive value, SVM support vector machine, NB Naïve Bayes.

[Figure: Figure 2 Receiver operating characteristic (ROC) curves of the discriminative performance of Models 1–4. Models 1 (quadratic Support Vector Machine [SVM]) and 2 (optimized Naïve Bayes [NB]) used Feature Set 1 that included all clinically important features. Models 3 (optimized SVM) and 4 (optimized NB) used Feature Set 2, which did not include pre-existing PVR as an input feature.]

For benchmarking purposes, we compared F1 scores of the 4 automated models to the ones obtained by manual coding. As shown in Supplementary Table S2, the performances were in the same order of magnitude for all models. The F1 scores were: 0.75 (vs 0.76) for Model 1, 0.78 (vs 0.81) for Model 2, 0.58 (vs 0.60) for Model 3 and 0.64 (vs 0.69) for Model 4.

## References

1. Pastor JC. Proliferative vitreoretinopathy: An overview. Surv. Ophthalmol. 1998;43:3–18. doi: 10.1016/s0039-6257(98)00023-x.
2. Pastor JC, de la Rua ER, Martin F. Proliferative vitreoretinopathy: Risk factors and pathobiology. Prog. Retin. Eye Res. 2002;21:127–144. doi: 10.1016/s1350-9462(01)00023-4.
3. Cowley M, Conway BP, Campochiaro PA, Kaiser D, Gaskin H. Clinical risk factors for proliferative vitreoretinopathy. Arch. Ophthalmol. 1989;107:1147–1151. doi: 10.1001/archopht.1989.01070020213027.
