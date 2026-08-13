# normfmt

*[English version](README.md)*

Arrête de corriger la Norme à la main. `normfmt` formate ton C à la Norme, écrit
le header, lance norminette et t'affiche ce qu'il reste. Terminal, vim, VS Code.
Une seule commande pour tout installer.

Sans sudo. Sans Homebrew. Marche sur un iMac du cluster comme sur ton portable,
~20 Mo sous `$HOME`.

## Ce qu'il fait

Les tabulations, les parenthèses, les lignes vides. Tout ce qui, dans la Norme,
n'a rien à voir avec ton algo et tout à voir avec la position des espaces. Tu
écris la logique, il s'occupe du reste.

Ce que tu écris :

```c
int	ft_max(int *tab, int len) {
  int i = 0;
  int max=tab[0];
  while(i<len)
  {
    if (tab[i] > max) max = tab[i];
    i++;
  }
  return max;
}
```

Ce que tu obtiens, header en haut avec ton login, et `norminette: OK!`

```c
int	ft_max(int *tab, int len)
{
	int	i;
	int	max;

	i = 0;
	max = tab[0];
	while (i < len)
	{
		if (tab[i] > max)
			max = tab[i];
		i++;
	}
	return (max);
}
```

Dix erreurs en moins, sans en lire une seule.

## Installation

```sh
git clone https://github.com/m2moiz/normfmt.git ~/normfmt
cd ~/normfmt
./tools/install.sh
```

Ça installe la commande, vim et VS Code d'un coup. Ouvre un nouveau terminal une
fois que c'est fini.

Il lit ton login dans `$USER`, ce qui est déjà correct sur une machine du
cluster. Sur ton propre portable, passe-le à la main :

```sh
./tools/install.sh --login <ton_login>
```

Ça finit dans le header de chaque fichier que l'outil touche, donc autant ne pas
se tromper.

**VS Code a besoin d'une extension.** Installe *Run on Save* de *emeraldwalk*
depuis la barre latérale Extensions. L'installeur le fait tout seul si la
commande `code` est dans ton `$PATH`, et te prévient sinon. Sans elle,
sauvegarder ne déclenche rien.

Autres options : `--core-only` si tu veux juste la commande sans qu'il touche à
ton éditeur, `--email <adresse>`, et `--uninstall` pour tout retirer.

## L'utiliser

```sh
normfmt ft_strlen.c     # formate un fichier, puis le vérifie
normfmt                 # tous les .c/.h sous le dossier courant
normfmt -n              # vérifie seulement, ne réécrit rien
```

Dans vim il se déclenche sur `:w`, et `:NormFmt` le lance à la demande. Mets
`let g:normfmt_on_save = 0` dans ton `.vimrc` si tu veux la commande sans
l'automatisme. Dans VS Code il tourne à la sauvegarde.

Son code de retour est celui de norminette, donc il s'insère tel quel dans un
Makefile :

```make
norm:
	@normfmt
```

## Avant de push

Un `main()` oublié et des fichiers que le sujet n'a jamais demandés : deux bons
moyens de récolter un zéro. `normsubmit` regarde ce que tu t'apprêtes à commit
et te dit ce qui cloche.

```
$ normsubmit

main() trouvé — le sujet ne demande souvent que la fonction :
  ./ft_strlen.c
  ./main.c  (ressemble à un fichier de test, à ne pas rendre du tout)
  fix: normsubmit --strip-main ./ft_strlen.c

fichiers de compilation — à supprimer avant de commit :
  ./a.out   ./ft_strlen.o   ./ft_strlen.dSYM   ./.DS_Store
  fix: normsubmit --clean

git suit déjà ces fichiers — ils SERONT rendus :
  ./main.c
  fix: git rm --cached <fichier>, puis ajoute-le au .gitignore
```

```sh
normsubmit --strip-main     # commente le main(), de façon réversible
normsubmit --restore-main   # le remet pour continuer à tester
normsubmit --clean          # supprime les fichiers de compil (il demande avant)
normsubmit --gitignore      # un .gitignore adapté à un repo 42
```

`--strip-main` commente la fonction derrière un marqueur, donc `--restore-main`
te rend le fichier d'origine octet pour octet et tu peux continuer à tester. La
version commentée passe toujours norminette.

**Il ne supprimera rien que tu aies écrit.** `--clean` affiche la liste et attend
un oui, et il ne retire que des fichiers de compilation : `.o`, `.a`, `a.out`,
`.dSYM`, `.DS_Store`, binaires compilés. Tes sources sont signalées, jamais
supprimées.

Il sort en 1 quand quelque chose cloche, donc il marche comme hook de pre-commit.
Quoi qu'il te dise, stage tes fichiers par leur nom. C'est avec `git add .` qu'on
perd des points.

## Ce qu'il ne corrigera pas

Tout ce qui demande une décision sur ton programme plutôt que sur sa mise en
forme. Un outil qui devinerait ici serait pire que pas d'outil du tout, donc il
te les affiche avec une piste à la place.

| Erreur Norme | Pourquoi c'est à toi de le faire |
| --- | --- |
| `TOO_MANY_LINES` | Découper une fonction, c'est un choix de conception |
| `TOO_MANY_FUNCS` | Dans quel fichier la déplacer ? |
| `TOO_MANY_VARS_FUNC` | Moins de variables, ou découpe la fonction |
| `FORBIDDEN_CS` | Transformer un `for` en `while` change le code |
| `ASSIGN_IN_CONTROL` | Sors l'affectation de la condition |
| `FORBIDDEN_CHAR_NAME` | Aucune règle ne transforme un mauvais nom en bon nom |
| `WRONG_SCOPE_COMMENT` | La Norme interdit les commentaires dans une fonction, et ce n'est pas à l'outil de supprimer les tiens |

## C'est safe sur mon code ?

Question légitime pour un truc qui réécrit tes fichiers. Quatre suites de tests
tournent avant chaque modification, et un fichier déjà propre ressort octet pour
octet identique.

```sh
python3 tools/tests/test_normfix.py     # 26 passed, 0 failed
python3 tools/tests/test_semantics.py   #  8 passed, 0 failed
python3 tools/tests/test_submit.py      # 23 passed, 0 failed
python3 tools/tests/test_fuzz.py 30     # 30 passed, 0 failed
```

La suite « semantics » compile chaque programme, l'exécute, le formate,
recompile et relance, puis vérifie que la sortie est identique octet pour octet.
Un formateur qui change ce que ton programme affiche est pire que pas de
formateur.

Le fuzzer massacre au hasard des programmes qui marchent : instructions collées
sur une ligne, déclarations fusionnées, tabulations remplacées par des espaces,
lignes vides éparpillées. Ensuite il vérifie que le résultat compile toujours,
affiche toujours la même chose, passe norminette, et ne bouge plus au deuxième
passage. 210 tours sur 6 graines passent. Il a trouvé deux vrais bugs, et c'est
la seule raison pour laquelle je fais confiance aux trois autres suites.

Il ne touche que les `.c` et les `.h`, et `normfmt -n` vérifie sans rien écrire.

`NORMFMT_FUZZ_SEED` change les mutations, `NORMFMT_FUZZ_KEEP=<dossier>` garde les
fichiers d'un tour raté.

## Quand ça casse

**`normfmt: command not found`** — ouvre un nouveau terminal. Si ça persiste,
lance `export PATH="$HOME/.local/bin:$PATH"`.

**`no python3 on PATH`** — lance `xcode-select --install`, puis relance
l'installeur.

**VS Code ne fait rien quand je sauvegarde** — l'extension Run on Save manque.
Cherche « Run on Save » de emeraldwalk dans la barre Extensions, puis lance
`./tools/install.sh --editors-only`.

**vim ne fait rien sur `:w`** — vérifie que `~/.vim/plugin/normfmt.vim` existe.
Sinon, relance `./tools/install.sh`. Neovim utilise `~/.config/nvim/plugin/`.

**Il a mis quoi, et où ?**

| Chemin | Quoi |
| --- | --- |
| `~/.42tools/` | virtualenv avec norminette + c_formatter_42, et les scripts |
| `~/.local/bin/` | `normfmt` et `normsubmit` |
| `~/.42toolsrc` | ton login et ton mail, utilisés pour le header 42 |
| `~/.vim/plugin/normfmt.vim` | format à la sauvegarde dans vim |
| `settings.json` de l'éditeur | une règle `emeraldwalk.runonsave`, avec sauvegarde préalable |

Tout est sous `$HOME`, donc ça survit entre les sessions, contrairement à
`~/goinfre`. `./tools/install.sh --uninstall` retire tout.

## Comment ça marche

Deux outils qui ne se connaissent pas, plus de la colle.
[c_formatter_42](https://github.com/cacharle/c_formatter_42), écrit par un
étudiant de 42, remet le code en forme en dix passes. La première est
clang-format avec une config taillée pour la Norme ; les neuf autres gèrent ce
que clang-format ne sait pas exprimer, comme mettre les valeurs de retour entre
parenthèses. norminette vérifie ensuite le résultat.

Tout le travail est dans l'écart entre les deux. Plutôt que d'écrire un parseur C
pour trouver les erreurs que le formateur laisse derrière lui, `normfix` demande
à norminette où elles sont, applique un correctif ciblé à cette ligne, relance le
formateur pour réaligner, et recommence jusqu'à ce qu'il ne reste rien de
corrigeable. Ajouter une erreur, c'est une entrée dans un dict.

Les erreurs que `normfix` règle en plus du formateur :

| Erreur | Correctif |
| --- | --- |
| `MULT_DECL_LINE` | `int a, b;` devient une déclaration par ligne |
| `MULT_ASSIGN_LINE` | `a = 1, b = 2;` devient une affectation par ligne |
| `TOO_MANY_INSTR` | `a = 1; b = 2;` devient une instruction par ligne |
| `NL_AFTER_VAR_DECL` | ligne vide après le bloc de déclarations |
| `NEWLINE_PRECEDES_FUNC` | ligne vide entre les fonctions |
| `CONSECUTIVE_NEWLINES` | réduites à une seule |
| `EMPTY_LINE_FUNCTION` | ligne vide supprimée |
| `EMPTY_LINE_FILE_START` / `EMPTY_LINE_EOF` | rognées |
| `SPACE_EMPTY_LINE` / `SPC_BEFORE_NL` | espaces en fin de ligne retirés |
| `SPACE_REPLACE_TAB` | les espaces laissés par l'aligneur deviennent une tabulation |
| `BRACE_SHOULD_EOL` | fichier qui ne finit pas par un retour à la ligne |
| `HEADER_PROT_*` | réécrit la garde d'un `.h` en `#ifndef FILE_H` / `# define FILE_H` / `#endif` |

Deux détails utiles si tu veux mettre les mains dedans. norminette donne des
colonnes *visuelles*, où une tabulation va jusqu'au prochain multiple de 4 : un
simple index de caractère pointe donc au mauvais endroit. Et quand deux erreurs
tombent sur la même ligne, le correctif structurel doit passer avant le correctif
cosmétique, sinon le cosmétique prend la ligne et le vrai problème n'est jamais
traité. Les deux sont sortis du fuzzer.

## Organisation

```
tools/
  normfmt            la chaîne : formatage, header, corrections, vérification
  normsubmit         contrôles avant push : main() oublié, fichiers parasites
  normfix.py         la boucle de correction pilotée par norminette
  42header.py        générateur de header 42
  vscode_setup.py    fusion des réglages éditeur, avec sauvegarde
  install.sh         installation en une commande
  editor/            plugin vim, réglages et tâches VS Code
  tests/             quatre suites
```

Python et bash. Le seul C++ de la pile est clang-format, livré précompilé dans le
wheel `c_formatter_42`, et c'est pour ça que rien ici n'a besoin d'un
compilateur.

## Crédits

- [norminette](https://github.com/42School/norminette) par 42 School
- [c_formatter_42](https://github.com/cacharle/c_formatter_42) par cacharle
- clang-format, de LLVM
