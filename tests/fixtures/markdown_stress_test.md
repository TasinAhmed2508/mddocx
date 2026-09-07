# Markdown Stress-Test Document

> A comprehensive Markdown test file containing typography, nested
> lists, tables, code, mathematical notation, calculus, complex
> analysis, derivations, diagrams, and graph definitions.

------------------------------------------------------------------------

## 1. Basic Markdown

This paragraph tests **bold**, *italic*, ***bold italic***,
~~strikethrough~~, `inline code`, and a [Markdown
link](https://example.com).

### Blockquote

> Mathematics is the language in which patterns can be expressed
> precisely.
>
> Nested quotation: \> This is a second-level blockquote.

### Horizontal rule

------------------------------------------------------------------------

## 2. Lists and Pointwise Content

### Unordered list

-   Algebra
    -   Linear algebra
        -   Vectors
        -   Matrices
        -   Eigenvalues
    -   Abstract algebra
-   Calculus
    -   Differentiation
    -   Integration
-   Analysis
    -   Real analysis
    -   Complex analysis

### Ordered list

1.  Define the function.
2.  Determine its domain.
3.  Compute the derivative.
4.  Locate critical points.
5.  Analyze the result.

### Task list

-   [x] Test headings
-   [x] Test equations
-   [x] Test tables
-   [x] Test code blocks
-   [ ] Test renderer-specific extensions

------------------------------------------------------------------------

# 3. Mathematical Foundations

## 3.1 Algebraic identities

Inline mathematics:

$$(a+b)^2 = a^2 + 2ab + b^2$$

and

$$
a^n-b^n=(a-b)\sum_{k=0}^{n-1}a^{n-1-k}b^k.
$$

## 3.2 Piecewise / pointwise function

$$
f(x)=
\begin{cases}
x^2, & x<0,\\
\sin x, & 0\le x\le \pi,\\
\ln x, & x>\pi.
\end{cases}
$$

Pointwise convergence example:

$$
f_n(x)=x^n,\qquad x\in[0,1].
$$

Then

$$
\lim_{n\to\infty}f_n(x)=
\begin{cases}
0,&0\le x<1,\\
1,&x=1.
\end{cases}
$$

------------------------------------------------------------------------

# 4. Calculus

## 4.1 Derivatives

For

$$
f(x)=x^x,
$$

take logarithms:

$$
\ln f(x)=x\ln x.
$$

Differentiate:

$$
\frac{f'(x)}{f(x)}=\ln x+1.
$$

Therefore,

$$
\boxed{f'(x)=x^x(\ln x+1)}.
$$

### Higher derivatives

$$
\frac{d^n}{dx^n}x^m
=
\frac{m!}{(m-n)!}x^{m-n},
\qquad n\le m.
$$

## 4.2 Integration

Basic indefinite integral:

$$
\int x^n\,dx=\frac{x^{n+1}}{n+1}+C,\qquad n\ne-1.
$$

Gaussian integral:

$$
I=\int_{-\infty}^{\infty}e^{-x^2}\,dx.
$$

Squaring,

$$
I^2=
\int_{-\infty}^{\infty}
\int_{-\infty}^{\infty}
e^{-(x^2+y^2)}\,dx\,dy.
$$

Using polar coordinates,

$$
I^2
=
\int_0^{2\pi}\int_0^\infty e^{-r^2}r\,dr\,d\theta.
$$

Since

$$
\int_0^\infty e^{-r^2}r\,dr
=
\frac12,
$$

we obtain

$$
I^2=\pi
\quad\Longrightarrow\quad
\boxed{I=\sqrt{\pi}}.
$$

## 4.3 Integration by parts

$$
\int u\,dv=uv-\int v\,du.
$$

Example:

$$
\int x e^x\,dx.
$$

Let $u=x$ and $dv=e^x dx$. Then $du=dx$ and $v=e^x$:

$$
\int xe^x\,dx
=
xe^x-\int e^x\,dx
=
e^x(x-1)+C.
$$

## 4.4 Improper integral

$$
\int_0^\infty e^{-ax}\,dx
=
\left[-\frac{1}{a}e^{-ax}\right]_0^\infty
=
\frac1a,
\qquad a>0.
$$

------------------------------------------------------------------------

# 5. Multivariable Calculus

Gradient:

$$
\nabla f=
\left(
\frac{\partial f}{\partial x_1},
\frac{\partial f}{\partial x_2},
\dots,
\frac{\partial f}{\partial x_n}
\right).
$$

Laplacian in Cartesian coordinates:

$$
\nabla^2 f
=
\frac{\partial^2 f}{\partial x^2}
+
\frac{\partial^2 f}{\partial y^2}
+
\frac{\partial^2 f}{\partial z^2}.
$$

Jacobian matrix:

$$
J_{\mathbf f}=
\begin{bmatrix}
\frac{\partial f_1}{\partial x_1} & \cdots & \frac{\partial f_1}{\partial x_n}\\
\vdots & \ddots & \vdots\\
\frac{\partial f_m}{\partial x_1} & \cdots & \frac{\partial f_m}{\partial x_n}
\end{bmatrix}.
$$

------------------------------------------------------------------------

# 6. Linear Algebra

Matrix multiplication:

$$
A=
\begin{bmatrix}
1&2\\
3&4
\end{bmatrix},
\qquad
B=
\begin{bmatrix}
5&6\\
7&8
\end{bmatrix}.
$$

Then

$$
AB=
\begin{bmatrix}
19&22\\
43&50
\end{bmatrix}.
$$

Eigenvalue equation:

$$
A\mathbf v=\lambda\mathbf v.
$$

Characteristic polynomial:

$$
\det(A-\lambda I)=0.
$$

A determinant:

$$
\det
\begin{bmatrix}
a&b\\
c&d
\end{bmatrix}
=ad-bc.
$$

------------------------------------------------------------------------

# 7. Complex Numbers and Complex Functions

Let

$$
z=x+iy,\qquad \bar z=x-iy,\qquad |z|=\sqrt{x^2+y^2}.
$$

Euler's formula:

$$
e^{i\theta}=\cos\theta+i\sin\theta.
$$

Hence

$$
e^{i\pi}+1=0.
$$

## 7.1 Powers and roots

If

$$
z=re^{i\theta},
$$

then

$$
z^n=r^ne^{in\theta}.
$$

The $n$th roots are

$$
z_k=
r^{1/n}
e^{i(\theta+2\pi k)/n},
\qquad
k=0,1,\dots,n-1.
$$

## 7.2 Complex exponential

For $z=x+iy$,

$$
e^z=e^x(\cos y+i\sin y).
$$

## 7.3 Complex sine and cosine

$$
\sin z=\frac{e^{iz}-e^{-iz}}{2i},
\qquad
\cos z=\frac{e^{iz}+e^{-iz}}{2}.
$$

## 7.4 Cauchy-Riemann equations

If

$$
f(z)=u(x,y)+iv(x,y),
$$

analyticity requires

$$
\frac{\partial u}{\partial x}
=
\frac{\partial v}{\partial y},
\qquad
\frac{\partial u}{\partial y}
=
-\frac{\partial v}{\partial x}.
$$

## 7.5 Contour integration

Cauchy's integral formula:

$$
f(a)=\frac{1}{2\pi i}
\oint_\gamma
\frac{f(z)}{z-a}\,dz.
$$

Residue theorem:

$$
\oint_\gamma f(z)\,dz
=
2\pi i
\sum_k \operatorname{Res}(f,z_k).
$$

Example:

$$
\oint_{|z|=2}\frac{e^z}{z}\,dz=2\pi i.
$$

------------------------------------------------------------------------

# 8. Infinite Series and Limits

Geometric series:

$$
\sum_{n=0}^{\infty}r^n=\frac{1}{1-r},
\qquad |r|<1.
$$

Taylor expansion:

$$
e^x
=
\sum_{n=0}^{\infty}\frac{x^n}{n!}.
$$

Sine:

$$
\sin x
=
\sum_{n=0}^{\infty}
(-1)^n\frac{x^{2n+1}}{(2n+1)!}.
$$

A classic limit:

$$
\lim_{x\to0}\frac{\sin x}{x}=1.
$$

------------------------------------------------------------------------

# 9. Differential Equations

First-order equation:

$$
\frac{dy}{dx}+P(x)y=Q(x).
$$

Integrating factor:

$$
\mu(x)=e^{\int P(x)\,dx}.
$$

Second-order homogeneous ODE:

$$
ay''+by'+cy=0.
$$

Characteristic equation:

$$
ar^2+br+c=0.
$$

Simple harmonic oscillator:

$$
\frac{d^2x}{dt^2}+\omega^2x=0,
$$

with solution

$$
x(t)=A\cos(\omega t)+B\sin(\omega t).
$$

------------------------------------------------------------------------

# 10. Probability and Statistics

Expectation:

$$
\mathbb E[X]=\sum_x x\,P(X=x)
$$

or, for a continuous variable,

$$
\mathbb E[X]=\int_{-\infty}^{\infty}x f_X(x)\,dx.
$$

Variance:

$$
\operatorname{Var}(X)
=
\mathbb E[X^2]-\mathbb E[X]^2.
$$

Normal density:

$$
f(x)=
\frac{1}{\sigma\sqrt{2\pi}}
\exp\left(
-\frac{(x-\mu)^2}{2\sigma^2}
\right).
$$

Bayes' theorem:

$$
P(A\mid B)
=
\frac{P(B\mid A)P(A)}{P(B)}.
$$

------------------------------------------------------------------------

# 11. Mathematical Tables

  -------------------------------------------------------------------------
  Function $f(x)$         Derivative $f'(x)$      Antiderivative
                                                  $\int f(x)\,dx$
  ----------------------- ----------------------- -------------------------
  $x^n$                   $nx^{n-1}$              $\frac{x^{n+1}}{n+1}+C$

  $e^x$                   $e^x$                   $e^x+C$

  $\sin x$                $\cos x$                $-\cos x+C$

  $\cos x$                $-\sin x$               $\sin x+C$

  $\ln x$                 $\frac1x$               $x\ln x-x+C$
  -------------------------------------------------------------------------

### Alignment test

  Left       Center         Right
  ------- ------------ ----------
  alpha      12.345           100
  beta       0.001          2,500
  gamma    $e^{i\pi}$    $\infty$

------------------------------------------------------------------------

# 12. Logic and Set Theory

$$
A\cup B,\qquad
A\cap B,\qquad
A\setminus B,\qquad
A^c.
$$

De Morgan's law:

$$
(A\cup B)^c=A^c\cap B^c.
$$

Logical equivalence:

$$
P\to Q
\equiv
\neg P\lor Q.
$$

Quantifiers:

$$
\forall x\in\mathbb R,\quad x^2\ge0,
$$

and

$$
\exists x\in\mathbb C:\quad x^2=-1.
$$

------------------------------------------------------------------------

# 13. Graphs

## 13.1 Mermaid flowchart

``` mermaid
flowchart TD
    A[Start] --> B{Is x positive?}
    B -- Yes --> C[Compute sqrt x]
    B -- No --> D[Use complex domain]
    C --> E[Return result]
    D --> E
```

## 13.2 Mermaid graph

``` mermaid
graph LR
    A((A)) --> B((B))
    A --> C((C))
    B --> D((D))
    C --> D
```

## 13.3 Mermaid sequence diagram

``` mermaid
sequenceDiagram
    participant U as User
    participant R as Renderer
    participant M as Math Engine
    U->>R: Load Markdown
    R->>M: Render LaTeX
    M-->>R: Equation output
    R-->>U: Display document
```

## 13.4 Function plot specification

Some Markdown renderers support function-plot extensions; others do not.
This fenced block is intentionally included as a parser test.

``` function
y = sin(x)
y = cos(x)
y = x^2 / 10
domain = [-10, 10]
```

## 13.5 ASCII graph

``` text
 y
 ^
 4|        *       *
 3|      *   *   *
 2|    *       *
 1|  *
 0+--------------------> x
   0  1  2  3  4  5
```

------------------------------------------------------------------------

# 14. Code Blocks

### Python

``` python
import numpy as np
import matplotlib.pyplot as plt

x = np.linspace(-2*np.pi, 2*np.pi, 1000)
y = np.sin(x) * np.exp(-0.1 * x**2)

plt.plot(x, y)
plt.xlabel("x")
plt.ylabel("f(x)")
plt.title("Damped sine function")
plt.grid(True)
plt.show()
```

### JavaScript

``` javascript
const square = (x) => x ** 2;

for (let x = -3; x <= 3; x++) {
  console.log(x, square(x));
}
```

### JSON

``` json
{
  "name": "markdown-stress-test",
  "math": true,
  "tables": true,
  "mermaid": true,
  "version": 1
}
```

------------------------------------------------------------------------

# 15. Advanced Derivation: Fourier Transform of a Gaussian

Use the convention

$$
\widehat f(k)
=
\int_{-\infty}^{\infty}
f(x)e^{-ikx}\,dx.
$$

For

$$
f(x)=e^{-ax^2},
\qquad a>0,
$$

we have

$$
\widehat f(k)
=
\int_{-\infty}^{\infty}
e^{-ax^2-ikx}\,dx.
$$

Complete the square:

$$
-ax^2-ikx
=
-a\left(
x+\frac{ik}{2a}
\right)^2
-\frac{k^2}{4a}.
$$

Therefore,

$$
\widehat f(k)
=
e^{-k^2/(4a)}
\int_{-\infty}^{\infty}
e^{-a(x+ik/(2a))^2}\,dx.
$$

Under the standard contour-shift argument,

$$
\boxed{
\widehat f(k)
=
\sqrt{\frac{\pi}{a}}
e^{-k^2/(4a)}
}.
$$

------------------------------------------------------------------------

# 16. Tensor / Indexed Notation

Einstein summation:

$$
v_i=A_{ij}x_j.
$$

Levi-Civita symbol:

$$
(\mathbf a\times\mathbf b)_i
=
\varepsilon_{ijk}a_jb_k.
$$

Metric contraction:

$$
ds^2=g_{\mu\nu}dx^\mu dx^\nu.
$$

------------------------------------------------------------------------

# 17. Physics-Style Equations

Schrödinger equation:

$$
i\hbar\frac{\partial}{\partial t}\Psi(\mathbf r,t)
=
\hat H\Psi(\mathbf r,t).
$$

Maxwell equations:

$$
\nabla\cdot\mathbf E=\frac{\rho}{\varepsilon_0},
$$

$$
\nabla\cdot\mathbf B=0,
$$

$$
\nabla\times\mathbf E
=
-\frac{\partial\mathbf B}{\partial t},
$$

$$
\nabla\times\mathbf B
=
\mu_0\mathbf J
+
\mu_0\varepsilon_0
\frac{\partial\mathbf E}{\partial t}.
$$

------------------------------------------------------------------------

# 18. Footnotes

A Markdown footnote may look like this.[^1]

Another reference can point to a longer note.[^2]

------------------------------------------------------------------------

# 19. Escaping and Special Characters

Literal Markdown characters:

\*asterisks\*, \_underscores\_, \# hash, \[brackets\], and
\`backticks\`.

HTML entities:

© & \< \> ---

------------------------------------------------------------------------

# 20. Final Stress Equation

$$
\boxed{
\int_{\partial\Omega}
\left(
\nabla u\cdot\mathbf n
\right)\,dS
=
\int_{\Omega}
\nabla^2u\,dV
}
$$

and a deliberately dense expression:

$$
\mathcal Z(\beta)
=
\operatorname{Tr}\left(e^{-\beta\hat H}\right)
=
\sum_{n=0}^{\infty}
e^{-\beta E_n},
\qquad
F=-\frac{1}{\beta}\ln\mathcal Z.
$$

------------------------------------------------------------------------

## End of Test

If your Markdown engine successfully renders most of this document, it
supports a broad set of Markdown, LaTeX/MathJax/KaTeX, fenced-code,
table, and diagram features.

[^1]: This is a basic footnote used to test footnote rendering.

[^2]: Mathematical notation in footnotes may be renderer-dependent:
    $e^{i\pi}+1=0$.
