# desemprego
Não leve nada que está aqui a sério, eu sou burro

# async_gif_player.py
Inicialmente era pra ser um gif player bosta mas agora também roda mp4, e possivelmente outros formatos, dependendo somente do opencv-python. 

Algum dia também terá suporte pra audio, só depende de quando eu descobrir pra qual file eu tenho que dar o open("soundfile") pra escrever diretamente.

~~Sim eu sou retardado mental~~

pra usar só fazer
```python
player = AsyncGifPlayer(filename, mode, char, console)
player.play()
```
- `filename` é o path para o arquivo a ser mostrado (atualmente .gif e .mp4)
- `mode` é o modo que a imagem será mostrada: `ascii` para mostrar em texto (bem smooth, mas apenas grayscale) e `color` para mostrar em cores (216 color ansi encoding)
- `char` o character a ser usado como pixel (só usado no modo `color`, default é o character espaço)
- `console` booleana para caso um novo console deve ser aberto ou se deve ser mostrado no mesmo terminal

Também pode ser utilizado no comandline simplesmente com
```
python async_gif_player.py filename mode --console --char #
```

# gravador_bosta.py
Um gravador de tela horroroso que pode dar output pra mp4 e gif e, novamente, pode salvar pra varios outros tipos por causa do opencv-python, mas eu tenho preguiça de atualizar isso (se vc quiser, sinta-se a vontade para implementá-lo).

É usado com
```
python gravador_bosta.py
```
Aperte uma vez capslock pra selecionar a área, outra vez para marcar a seleção. A terceira vez inicia a gravação e a quarta e última vez termina a gravação.
Por enquanto só pode ser salvo em gif e mp4, e não grava audio (_algum dia_). Só funciona em windows porque usa windows api.

# ascii_art.py
O programa que eu fiz que me levou para o caminho obscuro da programação inutil. 

Feito pra desenhar a imagem fornecida em _ascii art_, mas logo em sequência já deixou de ser apenas ascii art e passou a ter a imagem em ansi-color-code.

Eventualmente este daqui será inutil, porque eu pretendo adicionar essa funcionalidade no **async_gif_player** ao tentar abrir uma imagem.

É uma bosta.

Não use.


# letras_dancantes.py

É uma bosta.

Não use.
