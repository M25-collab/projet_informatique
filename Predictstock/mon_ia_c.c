#include <stdio.h>
#include <stdlib.h>
#include <math.h>

#define MAX_LINES        1000
#define NB_PREDICTIONS   10
#define WINDOW_SIZE      5
#define ADJUST_FACTOR    0.1  // 10% de correction sur la moyenne
#define SCORE_THRESHOLD  1.0

// Représente un point historique
typedef struct {
    double x;   // indice (jour)
    double y;   // prix
    double s;   // score d'actualité (inutile ici pour la correction)
} DataPoint;

// Lit tout l'historique CSV "jour,prix,score"
int load_historique(const char *filename, DataPoint data[]) {
    FILE *f = fopen(filename, "r");
    if (!f) { perror("Impossible d'ouvrir historique"); return 0; }
    char line[256];
    fgets(line, sizeof(line), f);  // saute l'en-tête
    int n = 0;
    while (n < MAX_LINES && fgets(line, sizeof(line), f)) {
        int jour; double prix, score;
        if (sscanf(line, "%d,%lf,%lf", &jour, &prix, &score) == 3) {
            data[n].x = (double)jour;
            data[n].y = prix;
            data[n].s = score;
            n++;
        }
    }
    fclose(f);
    return n;
}

// Calcule la moyenne glissante des WINDOW_SIZE derniers prix de data[0..train_n-1]
double calc_moyenne(DataPoint data[], int train_n) {
    double sum = 0;
    for (int i = train_n - WINDOW_SIZE; i < train_n; i++)
        sum += data[i].y;
    return sum / WINDOW_SIZE;
}

// Génère NB_PREDICTIONS à partir de base_moy
void generer_preds(double base_moy, double preds[]) {
    for (int i = 0; i < NB_PREDICTIONS; i++)
        preds[i] = base_moy + 0.5 * i;
}

// Écrit un array de prédictions dans un fichier
void ecrire_preds(const char *file, double preds[]) {
    FILE *f = fopen(file, "w");
    if (!f) { perror("Impossible d'écrire"); exit(1); }
    for (int i = 0; i < NB_PREDICTIONS; i++)
        fprintf(f, "%.2f\n", preds[i]);
    fclose(f);
    printf("→ Prédictions écrites dans %s\n", file);
}

// Calcule l'erreur moyenne entre preds[] et reals[]
double erreur_moyenne(double preds[], double reals[]) {
    double sum = 0;
    for (int i = 0; i < NB_PREDICTIONS; i++)
        sum += fabs(preds[i] - reals[i]);
    return sum / NB_PREDICTIONS;
}

// Ajuste la moyenne de base par un petit pas vers la première valeur réelle
double auto_correct(double base_moy, double pred0, double real0) {
    return base_moy + ADJUST_FACTOR * (real0 - pred0);
}

int main(int argc, char *argv[]) {
    if (argc != 4) {
        fprintf(stderr, "Usage : %s historique.csv sortie_init.txt sortie_corr.txt\n", argv[0]);
        return 1;
    }
    const char *hist_csv = argv[1];
    const char *out_init = argv[2];
    const char *out_corr = argv[3];

    DataPoint data[MAX_LINES];
    int n = load_historique(hist_csv, data);
    if (n < WINDOW_SIZE + NB_PREDICTIONS) {
        fprintf(stderr, "Pas assez de données (min %d, lu %d)\n",
                WINDOW_SIZE + NB_PREDICTIONS, n);
        return 1;
    }

    // On réserve les NB_PREDICTIONS derniers points pour validation
    int train_n = n - NB_PREDICTIONS;

    // Extraire les valeurs "réelles" depuis la partie réservée
    double reals[NB_PREDICTIONS];
    for (int i = 0; i < NB_PREDICTIONS; i++)
        reals[i] = data[train_n + i].y;

    // 1) Calcul de la moyenne glissante sur la partie 'train'
    double base_moy = calc_moyenne(data, train_n);

    // 2) Générer & écrire prédictions initiales
    double preds_init[NB_PREDICTIONS];
    generer_preds(base_moy, preds_init);
    ecrire_preds(out_init, preds_init);

    // 3) Évaluer l'erreur moyenne sur la partie réservée
    double err = erreur_moyenne(preds_init, reals);
    printf("Erreur moyenne (validation) : %.4f\n", err);

    // 4) Auto-correction très simple
    double base_corr = auto_correct(base_moy, preds_init[0], reals[0]);
    printf("Moyenne ajustée %.4f → %.4f\n", base_moy, base_corr);

    // 5) Générer & écrire prédictions corrigées
    double preds_corr[NB_PREDICTIONS];
    generer_preds(base_corr, preds_corr);
    ecrire_preds(out_corr, preds_corr);

    return 0;
}

