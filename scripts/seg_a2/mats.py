"""主歌一前半用到的显卡材质。导入本模块即完成注册。

钢笔墨迹（a2_ink）：墨迹的形状来自 strokes.ink_tex_data 生成的数据贴图（有向距离、书写时间、出墨量、飞白），
纸纤维来自 fibers.fiber_texture()，两者都按世界坐标取样，所以墨迹边缘的毛刺正好落在纸面的纤维上。
墨迹从笔尖经过的一刻出现，随后约半秒里顺着纤维渗开一点。出墨量决定颜色深浅和干的快慢：笔尖停留处墨多，
是近黑的蓝黑色，洇得也多，要两秒多才干；写得快的地方墨薄，颜色浅，一秒内就干成浅褐，还带着飞白的细白丝。
因为每个像素有自己的落墨时刻，同一个字里先写的笔画已经干成墨褐，后写的还是湿的蓝黑。"褪色"按旧墨水氧化的样子处理：颜色由墨褐变成浅棕，
浓度降低，最后几乎融进纸色。材质按正片叠底的方式输出（墨吸进纸里，纸纹透过墨色仍然可见）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import register_material  # noqa: E402

INK = r"""
uniform float ink_t0;        // 开始书写的时刻（秒）
uniform float ink_dur;       // 书写时长（秒）
uniform float ink_age;       // 褪色程度：0 为新写的字，1 为几乎褪尽
uniform float ink_em;        // 1 em 的世界长度
uniform vec3 ink_fresh;      // 湿墨颜色（墨足处的蓝黑）
uniform vec3 ink_dry;        // 干墨颜色（墨足处的墨褐）
uniform vec3 ink_old;        // 褪色后的颜色
uniform float ink_bleed;     // 洇开宽度（世界单位）
uniform float ink_gain;      // 整体浓度
uniform sampler2D fibers;
uniform float fib_tile;      // 纤维贴图一块的世界长度
uniform vec2 ink_wipe;       // 擦除：(进度 0–1, 方向 0 横向 1 纵向)，猫字化开时用；0 表示不擦

vec4 material(vec4 base) {
    vec4 d = texture(u_tex, v_uv);
    float sdf = (d.r - 2.0) * 0.1 * ink_em;          // 世界单位，字内为正
    float T = d.g;
    float dens = d.b;                                // 出墨量
    float fly = d.a;                                 // 飞白
    float t_ink = ink_t0 + T * ink_dur;
    float age = u_time - t_ink;
    float reveal = clamp(age / 0.016 + 0.5, 0.0, 1.0);
    if (reveal <= 0.0) return vec4(0.0);

    vec2 w = v_wpos.xy;
    vec2 q0 = w / fib_tile;
    vec2 q1 = mat2(0.8, 0.6, -0.6, 0.8) * w / (fib_tile * 0.41) + vec2(0.37, 0.11);
    vec4 f0 = texture(fibers, q0);
    vec4 f1 = texture(fibers, q1);
    float wick = f0.g * 0.6 + f1.g * 0.4;            // 吸墨程度，0–1
    float grain = (f0.b + f1.b) - 1.0;

    // 洇开：落墨后约半秒里沿纤维渗出。纸的吸墨性各处不同：低频噪声决定哪一段边缘洇得多，
    // 洇得多的地方边缘沿纤维起伏，偶尔有一两根纤维把墨引出一小段细须；其余的边缘只是略微毛糙
    float spread = ink_bleed * (0.45 + 0.55 * (1.0 - exp(-max(age, 0.0) / 0.45)));
    float lf = vnoise(w / (ink_em * 0.09), 7) * 0.6 + vnoise(w / (ink_em * 0.03), 9) * 0.4;
    float pch = smoothstep(0.45, 0.80, lf);
    float sp = spread * (0.30 + 1.0 * pch) * (0.45 + 0.95 * dens);   // 墨多处洇得开
    float e = sdf + sp * (wick - 0.40) * 0.55 + grain * sp * 0.45 + sp * (lf - 0.5) * 0.8;
    float px = max(fwidth(sdf), 1e-6);
    // 边缘有一圈很窄的淡墨过渡（墨被纸吸开的部分），宽度随洇开程度
    float core = smoothstep(-px - sp * 0.25, px, e);
    float out_d = max(-sdf, 0.0);
    float hair = smoothstep(0.88, 0.99, wick) * smoothstep(0.62, 0.88, lf) * exp(-out_d / max(sp * 0.8, 1e-6)) * 0.32;
    float cov = max(core, hair * (1.0 - core));

    // 墨色：墨足处深、墨薄处浅；湿的蓝黑 → 干的墨褐，墨越多干得越慢 → 褪色
    vec3 fresh = mix(mix(ink_fresh, vec3(0.42, 0.44, 0.52), 0.30), ink_fresh, dens);
    vec3 dried = mix(mix(ink_dry, vec3(0.62, 0.52, 0.42), 0.28), ink_dry, dens);
    float dry = 1.0 - exp(-max(age, 0.0) / (0.6 + 1.9 * dens));
    vec3 col = mix(fresh, dried, dry);
    col = mix(col, ink_old, smoothstep(0.0, 0.7, ink_age));
    // 飞白：沿运笔方向的细白丝，在纸纤维凸起处断开
    float flyk = fly * (0.75 + 0.5 * (wick - 0.4)) * (1.0 - 0.35 * dens);
    // 钢笔墨在笔画两侧积得多：离边缘一小段距离内更深；两笔叠压、起笔收笔处更深
    float rim = exp(-max(sdf, 0.0) / (ink_em * 0.012));
    float k = (0.90 + 0.10 * rim) * (0.70 + 0.30 * dens) * (1.0 + 0.06 * grain);
    float a = cov * reveal * ink_gain * k * (1.0 - ink_age * 0.92) * (1.0 - 0.85 * clamp(flyk, 0.0, 1.0));
    a *= mix(1.0, 0.8, hair * (1.0 - core));
    // 擦除（化成猫时，字的笔画按 ink_wipe.x 的进度从一侧消去）
    if (ink_wipe.y > 1.5) {
        // 裁掉 u > ink_wipe.x 的部分（猫走进墙角），边缘随纸纤维略有起伏
        float cut = ink_wipe.x + (wick - 0.4) * 0.006;
        a *= smoothstep(cut + 0.004, cut - 0.004, v_uv01.x);
    } else if (ink_wipe.x > 0.0) {
        float c = ink_wipe.y < 0.5 ? v_uv01.x : v_uv01.y;
        a *= smoothstep(ink_wipe.x - 0.08, ink_wipe.x + 0.08, c);
    }
    a = clamp(a, 0.0, 1.0);
    return vec4(col * a, a);
}
"""

CRT = r"""
// 显像管屏幕。平面的 0–1 坐标 v_uv01 覆盖屏幕玻璃外接的矩形；屏幕形状是带"枕形"外凸的圆角矩形，
// 由 crt_half（半宽、半高，平面尺寸的比例）、crt_rad（圆角半径，同单位）和 crt_bulge（四边外凸量）给出，
// 形状以外完全透明。画面内容是一幅灰度云图，经过：桶形畸变（玻璃弧面）→ 场不同步时的上下翻滚
// （黑色的场消隐条随之滚过）→ 字幕 → 雪花与串台的旧字 → 关机时的收缩 → 扫描线与荧光粉 → 玻璃上的反光。
uniform sampler2D cloud;      // 云图（灰度）
uniform sampler2D subs;       // 字幕（预乘 RGBA）
uniform sampler2D oldtxt;     // 串台的旧字（覆盖率，R）
uniform float crt_aspect;     // 平面宽高比
uniform vec2 crt_half;
uniform vec2 crt_pic;         // 光栅（画面）的半宽、半高（平面尺寸的比例）：屏幕玻璃可以比光栅大
uniform float crt_rad;
uniform float crt_bulge;
uniform float crt_on;         // 0 关、1 开（显像管预热时由暗到亮）
uniform vec3 crt_roll;        // 当前、1/60 秒前、2/60 秒前的翻滚偏移（以画面高为单位）
uniform float crt_snow;       // 雪花强度
uniform float crt_ghost;      // 旧字强度
uniform float crt_signal;     // 原节目信号的强度（雪花时减弱）
uniform vec2 crt_squash;      // 关机收缩：(竖直比例, 水平比例)，正常为 (1, 1)
uniform float crt_dot;        // 收缩成亮点后的余辉亮度
uniform vec2 cloud_off;       // 云图的平移（卫星云图的动画）
uniform float cloud_zoom;
uniform float glass_k;        // 玻璃反光强度
uniform vec3 glass_col;       // 关机时玻璃的颜色
uniform float crt_lines;      // 扫描线数
uniform float crt_hjit;       // 行不同步的水平抖动
uniform float crt_subk;       // 字幕的强度：雪花里字幕仍然读得出（字幕信号比画面强）

float rrect(vec2 p, vec2 h, float r) {
    vec2 q = abs(p) - h + r;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

vec3 program(vec2 sc, float roll) {
    // sc：屏幕坐标，(0,0) 左上、(1,1) 右下
    float y = sc.y + roll;
    float fy = fract(y);
    vec2 cuv = vec2(sc.x, fy);
    float lum = texture(cloud, (cuv - 0.5) / cloud_zoom + 0.5 + cloud_off).r;
    vec3 col = vec3(lum);
    // 场消隐条：每一帧画面的上下交界处有一条黑带，翻滚时可以看到它滚过
    float bar = smoothstep(0.0, 0.006, fy) * smoothstep(0.075, 0.069, fy);
    float vis = (abs(roll) > 1e-4) ? 1.0 : 0.0;
    col = mix(col, vec3(0.02), bar * vis);
    return col;
}

vec4 material(vec4 base) {
    vec2 uv = v_uv01;
    vec2 p = (uv - 0.5) * vec2(crt_aspect, 1.0);
    vec2 h = crt_half * vec2(crt_aspect, 1.0);
    // 枕形外凸：越靠近边的中点越往外
    vec2 hb = h + crt_bulge * vec2(1.0 - pow(p.y / h.y, 2.0), 1.0 - pow(p.x / h.x, 2.0)) * 0.5;
    float d = rrect(p, hb, crt_rad);
    float px = fwidth(d);
    float inside = 1.0 - smoothstep(-px, px, d);
    if (inside <= 0.0) return vec4(0.0);
    // 屏幕坐标（0–1）与桶形畸变：按光栅的大小，光栅以外是深色的玻璃
    vec2 n = p / (crt_pic * vec2(crt_aspect, 1.0));    // −1–1
    float r2 = dot(n, n);
    vec2 nd = n * (1.0 + 0.045 * r2);
    vec2 sc = nd * 0.5 + 0.5;
    // 关机收缩：画面先在竖直方向压成一条线，再在水平方向收成一个点；能量守恒，越收越亮
    vec2 sq = max(crt_squash.yx, vec2(1e-3));       // (水平, 竖直)
    vec2 c = (sc - 0.5) / sq + 0.5;
    float inpic = step(0.0, c.x) * step(c.x, 1.0) * step(0.0, c.y) * step(c.y, 1.0);
    float boost = min(1.0 / (sq.x * sq.y), 7.0);
    // 行不同步的水平抖动（每条扫描线错开一点）
    float line = floor(c.y * crt_lines);
    c.x += crt_hjit * (rnd(ivec2(int(line), 7), u_frame) - 0.5) * 0.04;
    vec3 pic = program(c, crt_roll.x) * 1.0;
    // 荧光粉余辉：翻滚时前两帧的画面留下渐弱的拖影
    vec3 trail = program(c, crt_roll.y) * 0.32 + program(c, crt_roll.z) * 0.14;
    pic = max(pic, trail);
    pic *= crt_signal;
    // 雪花：没有信号时显像管收到的噪声，水平方向略有拉长
    ivec2 gp = ivec2(int(c.x * 360.0), int(c.y * crt_lines));
    float sn = rnd(gp, u_frame * 3 + 1);
    float sn2 = rnd(ivec2(gp.x / 3, gp.y), u_frame * 3 + 2);
    float snow = clamp(sn * 0.75 + sn2 * 0.35 - 0.15, 0.0, 1.0);
    pic += vec3(snow) * crt_snow;
    // 串台的旧字：雪花里断续出现的红字
    float g = texture(oldtxt, c).r;
    pic = mix(pic, vec3(0.95, 0.28, 0.20) * (0.75 + 0.5 * snow), g * crt_ghost);
    // 字幕：随画面一起翻滚、一起被压扁，叠在雪花之上，雪花强时略带噪点
    vec4 sb = texture(subs, vec2(c.x, fract(c.y + crt_roll.x)));
    float sk = crt_subk * (1.0 - 0.25 * crt_snow * snow);
    pic = pic * (1.0 - sb.a * sk) + sb.rgb * sk;
    pic *= inpic * boost;
    // 扫描线：每条线中间亮、两边暗
    float sl = 0.62 + 0.38 * pow(abs(sin(c.y * crt_lines * 3.14159)), 0.7);
    pic *= mix(1.0, sl, clamp(sq.y * 1.2, 0.0, 1.0));
    // 四角暗一些（电子束斜射到边角，亮度下降）
    pic *= 1.0 - 0.38 * pow(r2 * 0.5, 1.5);
    pic *= crt_on;
    // 关机后的亮点：电子束停在屏幕中心，荧光粉的余辉慢慢熄灭
    float dd = length((sc - 0.5) * vec2(crt_aspect, 1.0));
    pic += vec3(0.95, 0.97, 1.0) * crt_dot * (exp(-dd * dd / 0.00012) * 3.0 + exp(-dd * dd / 0.0025) * 0.35);
    // 玻璃：关机时是灰绿色的玻璃，弧面上有窗户的反光和边缘的高光
    vec3 glass = glass_col * (0.75 + 0.35 * (1.0 - r2 * 0.4));
    // 窗户的倒影：一块带十字窗棂的柔边矩形，落在左上方，随弧面略微弯曲
    vec2 wq = (nd - vec2(-0.45, -0.50)) / vec2(0.30, 0.24);
    float wbox = (1.0 - smoothstep(0.75, 1.0, abs(wq.x))) * (1.0 - smoothstep(0.7, 1.0, abs(wq.y)));
    float mull = smoothstep(0.03, 0.07, abs(wq.x)) * smoothstep(0.03, 0.07, abs(wq.y + 0.15));
    float win = wbox * mull * (0.6 + 0.4 * smoothstep(1.0, -1.0, wq.x + wq.y));
    float rim = smoothstep(-0.10, -0.01, d / max(h.y, 1e-4)) * (0.5 + 0.5 * smoothstep(0.2, -0.6, n.y));
    // 弧面上一条宽而柔的斜向高光（台灯在左上方）
    float spec = exp(-pow((n.x * 0.55 + n.y * 0.85 + 0.62) / 0.16, 2.0)) * smoothstep(1.1, 0.2, length(n));
    vec3 refl = vec3(0.95, 0.92, 0.85) * (win * 0.10 + rim * 0.18 + spec * 0.07) * glass_k;
    vec3 col = glass + pic + refl;
    return vec4(col * inside, inside);
}
"""

register_material("a2_crt", CRT, defaults={
    "crt_aspect": 4.0 / 3.0, "crt_half": (0.48, 0.48), "crt_rad": 0.08, "crt_bulge": 0.02, "crt_on": 1.0,
    "crt_roll": (0.0, 0.0, 0.0), "crt_snow": 0.0, "crt_ghost": 0.0, "crt_signal": 1.0, "crt_squash": (1.0, 1.0),
    "crt_dot": 0.0, "cloud_off": (0.0, 0.0), "cloud_zoom": 1.0, "glass_k": 1.0, "glass_col": (0.07, 0.08, 0.075),
    "crt_lines": 240.0, "crt_hjit": 0.0, "crt_subk": 1.0, "crt_pic": (0.48, 0.48),
})

register_material("a2_ink", INK, defaults={
    "ink_t0": 0.0, "ink_dur": 0.3, "ink_age": 0.0, "ink_em": 1.0,
    "ink_fresh": (0.035, 0.045, 0.10), "ink_dry": (0.20, 0.13, 0.085), "ink_old": (0.52, 0.40, 0.29),
    "ink_bleed": 0.01, "ink_gain": 1.0, "fib_tile": 0.6, "ink_wipe": (0.0, 0.0),
})


# 由内向外显出：以 rv_c（平面 0–1 坐标）为中心，半径随 rv_p 增大，边缘带一点噪声的起伏。电视外壳从屏幕边缘
# 向外长出来，替换掉"口"的墨笔画。
register_material("a2_reveal", r"""
uniform float rv_p;
uniform vec2 rv_c;
uniform vec2 rv_h;
vec4 material(vec4 base) {
    // 到屏幕玻璃矩形的"盒距离"：玻璃边缘为 0，向外按玻璃的半宽、半高归一
    vec2 d = abs(v_uv01 - rv_c) / rv_h;
    float bd = max(d.x, d.y) - 1.0;
    float n = (vnoise(v_uv01 * vec2(31.0, 21.0), 13) - 0.5) * 0.12;
    float m = smoothstep(rv_p + 0.04, rv_p - 0.04, bd + n);
    return base * m;
}
""", defaults={"rv_p": 1.0, "rv_c": (0.5, 0.5), "rv_h": (0.3, 0.3)})
