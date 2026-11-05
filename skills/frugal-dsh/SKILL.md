---
name: frugal
description: Mide y baja el consumo de contexto/tokens de una sesión de DeepSeek Harness (DSH). Úsala cuando el usuario hable de tokens, créditos, límite, coste, sesión larga o lenta, cuando el contexto pase del 25 %, o antes de decidir entre seguir en la misma sesión o abrir una nueva con traspaso.
---

# Frugal · adaptación para DeepSeek Harness

Versión 0.1.0 · misma idea que la skill `frugal` de Claude Code, reescrita para DSH.
La de Claude depende de hooks, `/compact` y `settings.json`; aquí no existen. Esto usa lo que DSH
sí tiene: la proyección de sesión que el harness ya escribe en disco, subagentes y el selector de effort.

## 1. Medir, nunca estimar

```bash
python "%USERPROFILE%\.dsh\skills\frugal\scripts\estado_contexto.py"
```

Lee `~/.dsh/storages/session_projcache/sessions/*.json` (la sesión más reciente) e imprime ventana,
consumo, presión, desglose y facturado. `--json` para procesarlo; `--file RUTA` para una sesión concreta.

Dos cifras distintas, no las confundas:

| Cifra | Qué es |
|---|---|
| **consumo** (`surfaceTokens`) | lo que ocupa la conversación ahora |
| **presión** (`pressureTokens`) | consumo + reserva para la próxima respuesta; es la que suele mostrar la interfaz |

## 2. Umbrales

| % de ventana | Qué hacer |
|---|---|
| < 25 % | normal. No toques nada y no hables de tokens. |
| 25–45 % | lecturas pesadas → subagente. No cargar skills grandes sin necesidad. Cerrar temas. |
| 45–70 % | proponer traspaso: actualizar `ESTADO.md`, entrada en `BITACORA.md`, sesión nueva. |
| > 70 % | traspaso inmediato. No empezar trabajo nuevo. |

## 3. Palancas, por impacto

1. **Subagente** para exploración: 30 archivos leídos allí no entran aquí; vuelve solo la conclusión.
2. **Effort bajo** para ejecución mecánica (cortar clips, renombrar, transcribir). `high` solo para razonar.
3. **Sesión nueva + estado escrito** en vez de arrastrar 300 k de historial.
4. **Skills bajo demanda**: un `SKILL.md` cargado son 3–10 k tokens. No cargar "por si acaso".
5. **No re-leer** lo que ya está en el contexto.

## 4. Disciplina de lectura (lo que de verdad ahorra)

- Busca antes de leer: `grep`/`glob` primero; abre solo el archivo que coincide.
- Archivos largos: lee por rangos (`offset`/`limit`), nunca enteros.
- Edita por parche (`edit`), no reescribas el archivo completo.
- Salidas de comandos: recorta (`Select-Object -Last 25`). Nunca logs completos.
- No releas lo que ya está en el contexto ni reexpliques decisiones cerradas.
- Exploración pesada → subagente, y quédate solo con el resultado.

## 5. Traspaso sin archivo nuevo

El estado del proyecto (`ESTADO.md`) + la última entrada de la bitácora **son** el handover.
No crear `HANDOVER.md`, `TRASPASO.md` ni similares: es el mismo contenido en otro sitio y vuelve
el problema de las dos versiones de la verdad.

## 6. Lo que esta skill NO hace

- No reduce el coste por token ni amplía la ventana: mide y ordena.
- No cambia el modelo ni el effort: eso es el selector de la interfaz.
- No impide leer de más: eso es disciplina, y la disciplina se sostiene con reglas globales
  (`~/.dsh/AGENTS.md`) más esta skill, no con la skill sola.

## 7. Auditoría

Cuando el usuario pida "auditar frugal" o "¿cómo vamos?": corre el script, compara con la medición
anterior y propón **un** cambio concreto (no cinco). Registrar el cambio en `CHANGELOG.md`.
