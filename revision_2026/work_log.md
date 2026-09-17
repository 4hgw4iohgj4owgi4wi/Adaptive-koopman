# VT-2026-05393 重投稿工作记录

> 项目：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`  
> 执行原则：以关闭审稿意见为目标；核心证据达不到验收条件时停止对应路线并输出解决方案，不以调参掩盖负结果。

## 2026-08-18

### W0001｜启动与版本条件检查

- 对应任务：T0、T2.1。
- 执行动作：远程连接 5080，确认项目根目录、关键入口文件和 `revision_2026` 状态。
- 事实结果：
  - 项目根目录存在；
  - `tf14_runtime.py`、`tf14_pre.ipynb`、`README.md` 存在；
  - `revision_2026` 尚不存在；
  - 项目根目录不是 Git 仓库，无法执行原任务书中的 Git tag、commit hash 和 `git status` 冻结。
- 判断：版本追踪前提缺失，但不阻塞 T0；改用只读文件快照、SHA-256 清单、运行 manifest 和逐次变更记录。
- 改动：尚未修改原项目代码。
- 下一步：建立 `revision_2026`，复制原始审稿信、论文源文件与任务树，生成基线哈希清单。

### W0002｜建立 T0 基线工作区

- 对应任务：T0.1、T2.1。
- 执行动作：
  - 新建 `revision_2026/00_baseline` 至 `08_manuscript`、`solutions` 等目录；
  - 复制原审稿信、原论文 `main.tex`、任务树、`tf14_runtime.py`、`tf14_pre.ipynb` 和项目 README；
  - 对 TF14 顶层入口、`control_files` 与 `dynamics/learned_models_control` 中 57 个核心源文件生成 SHA-256 清单。
- 产物：
  - `00_baseline/source_sha256_manifest.csv`；
  - `00_baseline/baseline_metadata.json`；
  - `00_baseline/manuscript.original.tex`；
  - `00_baseline/reviewer_decision.txt`；
  - `00_baseline/task_tree.md`。
- 改动：只新增独立的 `revision_2026` 工作区；未覆盖任何原始代码和原始实验数据。
- 验收：T0 基线材料齐全；因原项目无 Git，版本追踪降级为 SHA-256 + 快照 + 工作记录。

### W0003｜IRSP 实现与论文表述一致性初审

- 对应任务：T3.1、T4.1。
- 检查文件：
  - `control_files/tf11_a1/core_utils.py`；
  - `control_files/tf11_a1/mpc_helpers.py`；
  - `tf14_runtime.py`；
  - 原论文 IRSP 与 Theorem 1 段落。
- 事实结果：
  - 实际主实现默认 `enforce_norm_bound=False`；
  - 初始模型与在线更新调用均从配置读取 `input_aware_enforce_norm_bound`，默认仍为 `False`；
  - fallback helper 只实现 sampled spectral-radius projection，没有连续域 norm certificate；
  - `gamma_norm = clip((radius-||A+||₂)/budget,0,1)` 在 `||A+||₂>radius` 时返回 0，但 `gamma=0` 后 `A_eff=A+`，不能保证 `||A_eff||₂≤radius`；
  - 因此现有实验只能支撑“有限采样点谱半径审计”，不能支撑连续输入域 contraction、递归可行性或闭环稳定性。
- 判断：审稿人 R2-2 与 R3-4 的质疑成立；在 T3 修正和 G3 通过前，停止使用原 IRSP 结果作为理论支撑。
- 改动：尚未修改原 IRSP 实现；先创建独立反例测试和审计文件，避免污染原结果。

### W0004｜Eq. (22) 反例测试

- 对应任务：T3.1、R3-4。
- 新增文件：`03_irsp/test_eq22_counterexample.py`。
- 环境过程：
  - 默认 `E:\anaconda\python.exe` 缺少 `torch`；
  - `conda run -n pytorch_new` 触发 OpenMP runtime 冲突；
  - 项目可用解释器确认为 `E:\anaconda\envs\pytorch_new\python.exe`；
  - 为避免用不安全的 `KMP_DUPLICATE_LIB_OK` 绕过冲突，反例测试隔离复写原公式与 spectral projection 的精确数值逻辑，仅依赖 NumPy。
- 实际结果：
  - `radius=0.998`；
  - `rho(A+)=0.9`；
  - `||A+||₂=10.0719854`；
  - 原公式返回 `gamma_norm=0`、`gamma_applied=0`；
  - 但 `||A_eff(0)||₂=10.0719854>0.998`。
- 产物：`03_irsp/eq22_counterexample_result.json`。
- 验收：成功复现 reviewer R3-4 指出的逻辑错误。

### W0005｜原实验 runner 可运行性与 noDelay 配对冒烟检查

- 对应任务：T2、T6.2 的运行链检查。
- 使用解释器：`E:\anaconda\envs\pytorch_new\python.exe`。
- 运行：E2、seed 3091、`sine_mixed_fault_noise`、`full_tf14` vs `no_delay_compensation`，独立输出目录 `06_experiments/smoke_original`。
- 事实结果：两组均成功完成 1000 步，证明原 runner、CUDA、模型加载与日志流水线仍可运行。
- 单种子诊断：
  - full：lateral RMSE 0.0461973，longitudinal RMSE 0.4673333，connection max 0.0530167，force peak 1476.6865；
  - noDelay：lateral RMSE 0.0465514，longitudinal RMSE 0.4670500，connection max 0.0540688，force peak 1429.4239；
  - full 的横向误差仅低约 0.000354 m，同时纵向误差和 force peak 更高。
- 判断：该结果为 E1 单种子诊断，不构成 delay compensation 支撑证据；只证明任务链可运行。
- 改动：未修改原 runner；全部输出写入 `revision_2026`。

### W0006｜实际 31D Koopman 模型的 IRSP 连续域审计与 G3 停止

- 对应任务：T3.2–T3.4、G3、R2-2、R3-4。
- 新增文件：`03_irsp/extract_actual_irsp_model.py`。
- 操作：通过原实验 runner 引导 `tf14_pre.ipynb` 环境，重新拟合并提取实际 31×31 bilinear Koopman 矩阵；未修改原代码。
- 实际结果：
  - 拟合样本数 805824，lifted RMSE 0.00549320；
  - 原实现使用 96 个输入样本；
  - `gamma_sampled=gamma_applied=0.2465813`；
  - sampled max spectral radius = 0.998；
  - `input_aware_enforce_norm_bound=False`；
  - 投影后 `rho(A+)=0.9920000`，但 `||A+||₂=1.0980027`；
  - 连续输入盒下 bilinear norm budget = 0.2281105；
  - 三角上界 = 1.3261132；
  - 重新计算 `gamma_norm=0`，且仅缩放 bilinear 项无法使 `||A_eff||₂≤0.998`。
- 产物：
  - `03_irsp/actual_irsp_matrices.npz`；
  - `03_irsp/actual_irsp_audit.json`。
- 结论：现有 IRSP 只能支撑有限采样谱半径审计，不能支撑连续输入域 contraction、recursive feasibility 或 stability。G3 停止条件触发。
- 停止动作：按用户要求停止继续执行 T4–T10 和任何用于维持原 IRSP 主张的大规模实验，先输出解决方案报告。

### W0007｜连接器物理作用链审计

- 对应新请求：检查连接器是否真正作用于货物、转弯时是否产生影响、能否判断各连接点合力方向和撕裂。
- 检查文件：
  - `control_files/rigid_payload_connection_compliance_a1_v1.py`；
  - `dynamics/cacalv3_payload_a1.py`；
  - `tf14_runtime.py`；
  - seed 3091 的 `connection.csv`、`payload_force.csv`、`control_spread.csv` 和 `summary.json`。
- 事实结果：
  - 现连接器类只维护每车 `ds/dey/dpsi` 及其速率；`k/c` 出现在相对状态二阶滤波方程中，不是 N/m、N·s/m 的物理刚度阻尼；
  - 连接器更新只由车辆控制指令相对团队平均指令的差驱动，并施加 zero-mean 与硬裁剪；
  - 更新后只把相对偏移叠加到由团队状态生成的四个角点状态，间接影响下一步车辆控制；
  - 团队/货物状态由 `safe_FK_step` 的等效自行车模型直接更新，未输入四点连接力和力矩；
  - `compute_payload_force_metrics` 只计算 `m_p a_x`、`m_p a_y`、`I_z r_dot` 和准静态角点法向载荷转移；不读取连接器状态；
  - 现有日志没有每个连接点的 `Fx/Fy`、方向角、轴向拉力、剪力或反作用力。
- 判断：当前连接器是控制/运动学 compliance surrogate，不是物理连接器模型；无法据此判断每点受力方向或货物是否受到撕裂力。

### W0008｜连接器 on/off 与转弯载荷诊断

- 新增脚本：
  - `07_force_validation/run_connector_role_audit.py`；
  - `07_force_validation/analyze_aggregate_turn_force.py`。
- connector on/off：seed 3092、同一 `sine_mixed_fault_noise` 场景，单种子配对诊断。
- on-minus-off 结果：
  - lateral RMSE `+1.432e-05 m`；
  - longitudinal RMSE `+2.731e-04 m`；
  - aggregate force peak `+107.944 N`；
  - aggregate force RMS `+2.593 N`；
  - 两者均完成全路径。
- 连接器变形代理与曲率：`corr(|kappa|, max deformation)=-0.1148`；高曲率四分位平均变形 0.002265，低曲率四分位 0.002526。
- 判断：在该单种子诊断中，现 surrogate 对整体闭环结果影响很小，且变形代理没有随曲率增强；其激励主要来自车辆命令差和 lag，而不是物理转弯载荷。
- aggregate payload proxy 的曲率分组（seed 3091）：
  - 高曲率组 mean `|Fy|=204.36 N`，低曲率组 131.77 N；
  - 高曲率组 planar resultant RMS=626.07 N，低曲率组 490.45 N；
  - 高曲率组 corner-load spread mean=246.42 N，低曲率组 182.58 N。
- 判断：转弯确实提高了当前等效货物模型的横向惯性载荷和载荷转移，但这不是四连接点力的结果，不能用于撕裂判断。
- 输出：`07_force_validation/connector_role_audit_seed3092/connector_role_audit.json`、`07_force_validation/aggregate_turn_force_audit.json`。

### W0009｜四车连接双向耦合模型优先任务书 V2

- 对应新请求：参考 `D:\PDxc\Koopman_Train` 的连接方式，把四个平面连接力同时施加到四辆单车、货物和车辆阵列系统，并完善弯道方向判断。
- 复核文件：
  - `Koopman_Train/src/coupled_transport_dynamics.py`；
  - `Koopman_Train/src/payload_force_proxy.py`；
  - `Koopman_Train/src/system_force_allocator.py`；
  - `Koopman_Train/src/koopman/physics_prior.py`；
  - `Koopman_Train/方案_连接器力约束与出弯加速限幅_20260812.md`。
- 事实结果：
  - 参考项目存在带圆周间隙的单边径向弹簧—阻尼连接模型，并在联合 RK4 各阶段重算作用—反作用力；
  - 参考 plant 是三车，需要改成四车；三点静定支撑公式不能直接扩为四点；
  - 参考 plant 可输出二维力并让连接力进入三辆车动力学，但目标系统还需显式车辆侧锚点力臂，确保连接平动力产生单车横摆力矩；
  - 参考 physics prior 的连接快通道仍是代理，且曾省略连接反力进入车辆块，不能作为目标 plant；
  - 参考默认 `k/c/间隙/额定力` 只能作初始仿真假设，不能冒充四车实物参数。
- 术语修正：本任务的“水平/竖直两个分力”定义为地面平面内 `Fx/Fy`。若实际指重力方向 `Fz`，必须另建三维车身/悬架模型，不能直接进入当前 `vy` 方程。
- 改动：整篇重写 `connector_physics_and_tearing_rewrite_plan.md`，主线改为“模型合同 → 四连接器 → 四车/货物联合 plant → 阵列守恒/等效 4WS → 控制与 Koopman → 弯道方向 → 内部载荷 → 论文”。
- 判断：本轮只修改任务书和工作记录，未修改原始 plant；下一步应从新增模块和解析单元测试开始，不应直接覆盖旧 surrogate。

### W0010｜四车—四连接器—货物首版物理模型

- 对应任务：M1、M2首版和100m验收准备。
- 新增简洁文件：`revision_2026/model/model.md`、`four_vehicle_coupled.py`、`test_model.py`、`run_100m.py`。
- 实现：四车和货物各自六状态；四个圆周间隙径向弹簧—阻尼连接；作用反作用；车辆/货物锚点力矩；联合RK4每stage重算连接力；四点平面Fx/Fy、辅助Fz、系统角动量等效横摆和对向载荷代理。
- 解析测试：本机与5080均通过间隙零力、方向、作用反作用、单车/货物平动和单车横摆耦合。
- 原项目状态：未覆盖旧 `cacalv3_payload_a1.py`、旧surrogate或 `tf14_runtime.py`，避免未验收模型污染原结果。

### W0011｜100m首轮验收失败与停止

- 工况：`v0=2m/s`；前30m `a=0.5m/s²`；虚拟前/后轴 `+4°/−2°` 持续5s，再 `−4°/+2°` 持续5s；随后按剩余距离减速。
- 运行环境：5080，`E:\anaconda\envs\pytorch_new\python.exe`。
- 基准/收敛步长：`dt=0.002s` 和 `0.001s`。
- 通过项：状态有限；内部力闭合残差0；正反阶跃平均货物Fy符号相反；三项步长差远小于5%。
- 失败项：60s只完成 `52.1515m`；连接力峰值 `20.910kN`，超过参考额定12kN和极限15kN；系统横摆峰值 `0.7973rad/s`；前后张开代理峰值 `27.598kN`。
- 判断：四车开环转向分配与阵列几何不相容，且连接/锚点参数未标定；本次不能作为100m通过或货物安全证据。
- 停止动作：停止接入原plant、控制器、Koopman和论文实验；新增 `stop.md`，保留失败CSV、JSON和PNG。

### W0012｜验收图片回传与视觉核验

- 回传目录：`D:\PDxc\Review\model_results`。
- 图片：`overview.png`、`forces.png`、`cargo.png`、`directions.png`、`trajectory.png`。
- 视觉核验：
  - `overview.png` 清楚显示正阶跃后速度从约5.8m/s快速下降并最终停滞；
  - `forces.png` 分开显示四点平面Fx/Fy与辅助支撑Fz，Fz保持为正但出现明显载荷转移；
  - `cargo.png` 显示连接器峰值越过12kN额定线以及前后张开代理脉冲；
  - `directions.png` 的四阶段箭头与数值标签可读，正反阶跃方向明显变化；
  - `trajectory.png` 显示四车未维持刚体阵列，是模型/转向分配失败的直接空间证据。
- 判断：图片与JSON/CSV结论一致，可作为失败证据；不得包装成100m验收通过图。

### W0013｜共同ICR版本复核与逐项执行书

- 新请求：以已经完成转向分配、力传递看起来正常的模型为基础，重新设计代码修改和逐项实验执行顺序。
- 实际复核：5080新增 `steering_allocator.py`、`test_steering.py`、`steer.md`、`result.md`，且 `run_100m.py` 已更新。
- 权威结果：`run100_icr/report.json` 显示完成100.0005m、连接峰值2.220kN、系统横摆峰值0.1431rad/s、ICR法向残差1.06e-14m/s、作用反作用残差0、dt/2收敛通过。
- 独立判断：可以作为候选基线；但连接参数和车辆锚点未实物标定，方向反馈与零和速度修正尚未分别消融，不能直接称最终物理模型或安全证据。
- 新增简洁执行书：`run.md`。
- 执行顺序：冻结基线→ICR/消融→连接器→单车→货物/阵列→分阶段→100m→参数适用域→原项目接入→论文。
- 本轮只更新执行MD和工作记录，未修改代码。

### W0014｜控制与网络实验顺序更新

- 用户指定顺序：当前100m工况先加通讯干扰并看受力/误差；正常通讯单移线AKE-M与NR方法对比；回头弯对比；最后做通讯扰动和DoS对比。
- 缩写核对：项目正式方法名为 `NR-KDCC`，基线为 `AKE-M`。
- 修改：在 `run.md` 新增C0–C4和N0/N1。
- 核心逻辑：C0不预设保护必要性，必须由可重复的受力、误差或约束退化证据触发；网络trace跨方法冻结重放。
- 网络改进：timestamp/sequence/AoI、延迟外推、AoI增长不确定性、质量加权、约束收紧、DoS本地fallback、恢复滞环和软恢复。
- 对比顺序：C0当前工况诊断→C1 clean单移线→C2 clean回头弯→C3 delay/loss/DoS→C4统计与证据审查。
- 公平性：AKE-M和NR-KDCC必须使用同一新物理plant、ICR分配、约束、调参预算和trace；禁止新旧plant结果直接比较。
- 本轮只修改MD和工作记录，未修改代码或启动实验。

### W0013｜文献ICR转向分配、纯运动学门与100m因果复测

- 文献依据：Zhao等的4WD-4WS共同ICR/Jacobian无侧滑约束；Zhang等的多轴Ackermann显式转角关系；Yamaguchi等的车式机器人协同搬运连接点运动学。
- 新增简洁文件：`steer.md`、`steering_allocator.py`、`test_steering.py`、`result.md`。
- 关键修正：虚拟前后轴角仅用于求阵列ICR；分别计算四车目标车体切向方向、速度和自身自行车转向。增加车体方向反馈与四车零均值速度修正。
- 纯运动学测试：直行退化、ICR法向速度残差、左右镜像、同号横摆前馈、零和速度分配全部通过；最大法向残差 `1.06e-14m/s`。
- 同工况100m复测：完成 `100.0005m`；连接峰值 `2.220kN`；系统横摆峰值 `0.1431rad/s`；正/反阶跃平均货物Fy分别 `+1495.83N/−1580.52N`；连接力未超参考额定。
- 步长：`dt=0.002/0.001s` 三个峰值指标相对差均小于0.1%，收敛门通过。
- 对照判断：相对旧分配，连接峰值约下降89.4%，系统横摆峰值约下降82.1%，100m由失败变通过；强证据支持旧转向映射是首要因果变量。
- 限制：连接/锚点参数仍未实物标定；方向反馈与速度修正是工程扩展，需继续消融；没有材料证据，不能给出实际撕裂结论。

### W0015｜候选基线冻结与T0–T1复跑

- 冻结对象：`four_vehicle_coupled.py`、`steering_allocator.py`、`test_model.py`、`test_steering.py`、`run_100m.py`、`run100_icr/report.json`，SHA256写入`model/base.md`。
- 5080解释器：`E:\anaconda\envs\pytorch_new\python.exe`。
- 事实结果：模型测试通过零间隙、方向、作用反作用、车辆/货物/横摆耦合；转向测试通过直行、共同ICR无侧滑、镜像、同号横摆前馈和零和速度分配。
- 判断：T0/T1通过；冻结的是数值候选基线，不代表连接器实物参数已标定。

### W0016｜T2–T4连接器—单车—货物—阵列力链解析验证

- 新增：`model/test_force.py`。
- 覆盖：4连接点×4方向×加载/卸载速度共32个单点算例，以及纵向合力、横向合力、前后张开、左右张开、纯横摆六类组合载荷。
- 事实结果：作用反作用最大误差`0 N`；单车增量导数最大误差`1.44e-15`；货物合力和合矩重构误差均为`0`。
- 关键机理证据：前后/左右张开算例的系统净力均为`0`，但对应张开代理均为`600 N`；纯横摆净力为`0`而合矩为`3231.10 N·m`。
- 判断：内部力不能用系统总合力替代；当前可判断连接点对向受拉模式，仍不能在缺少材料/截面数据时声称实际撕裂。

### W0017｜T5–T7分阶段、100m消融与参数适用域

- 新增：`model/run_scan.py`；输出为同一100m工况的功能消融和参数扫描。
- 完整模型：完成100m，连接峰值`2220.2 N`。
- 因果消融：仅前馈在`55.735 m`失败、峰值`15.786 kN`；仅速度修正在`49.803 m`失败、峰值`15.837 kN`；错误直接复制转角在`52.151 m`失败、峰值`20.910 kN`；前馈+方向反馈完成、峰值`2.571 kN`。
- 参数扫描：k/c、间隙、载荷、锚点和0.5/1/2度转向样本均完成；本批未覆盖计划中的全部速度、附着、4度转向和单连接器退化轴。
- 判断：共同ICR几何与方向反馈是当前稳定性的主要组成；零和速度修正降低内力但不是唯一稳定来源。T5/T6通过，T7仅通过已执行的有限扫描域，不能外推到未扫工况。

### W0018｜C0当前100m工况通讯退化诊断

- 新增：`model/channel.py`、`test_net.py`、`run_comm.py`；控制周期`0.02 s`，plant步长`0.002 s`，seed `3101–3105`配对重放。
- 网络层：有向链路、timestamp/sequence、时延、丢包、乱序和Gilbert–Elliott突发丢包；测试通过确定性、方向性、clean透明性和退化边界。
- 事实结果：clean/light/medium/heavy的PDR分别为`1.000/0.978/0.825/0.495`；最大AoI分别为`0/5.4/26.2/63.2`个控制周期。
- 受力与误差：总连接力P99不单调；重度网络的开裂型内力P99增至`1831.5 N`，货物相对clean轨迹偏差RMSE增至`2.354 m`。
- 判断：保护必要性由“内部张开载荷+轨迹偏差”重复退化触发，不由总连接力峰值单项触发；证明的是此仿真工况中的因果链，不是网络攻击下实物安全结论。
- 产物：`model/comm/need.json`、`need.png`。

### W0019｜N0–N1通讯保护配对实验

- 修改：`run_comm.py`增加序列拒收、AoI外推、质量加权、AoI>10周期的本地降级和软恢复；新增`run_protect.py`。
- 因果边界：保护器只使用已到达包、时间戳、序列号和历史状态，不读取未来trace或真实远端状态。
- clean透明性最大数值差`1.31e-13`。
- 相对无保护：medium/heavy货物偏差RMSE分别下降`49.6%/84.4%`；开裂型内力P99分别下降`40.5%/27.0%`；所有seed完成100m。
- 代价：heavy总连接力P99上升`41.2%`；因此只能称轨迹/张开载荷保护有效，不能称所有受力指标全面改善。
- 验收：按预先门槛通过；该总合力代价列为C1–C4必须报告的Pareto风险。
- 产物：`model/protect/protect.json`。

### W0020｜C1/C2接入前原控制运行器审计

- 核查：`pinn/legacy/experiments/tf14_runtime.py`、`tf14_remaining_experiments_20260509/run_tf14_remaining_experiments.py`、stage5场景与hairpin runner。
- 事实：原运行器把四车命令经coordinator聚合为单个`u_team`，再由`safe_FK_step`推进等效自行车team state；四个local state由旧compliance surrogate从team state生成。
- 方法身份：项目元数据把`baseline`标为`AKE-M`，把`tf14_phase_role/full_tf14`作为提出方法；另有AKE-A任务对齐复现，不能与AKE-M混称。
- 判断：旧AKE-M/NR结果不满足“同一新四车物理plant”的公平门，不能直接用于C1/C2。下一步先实现可选coupled plant适配器并做clean单种子冒烟；若不能完成或连接力越限，按停止门结束。

### W0021｜原控制器接入四车耦合物理模型

- 修改：根目录 `tf14_runtime.py` 增加可选 `plant_mode=four_vehicle_coupled`；新增 `model/adapter.py`，把项目真实AKE-M/NR-KDCC控制输出经共同ICR分配器映射到30维四车—货物物理plant。
- 运动学映射：等效转角拆为虚拟四轮转向，前轴比例 `2/3`、后轴比例 `-0.5`，小角度下保持 `delta_f-delta_r≈delta_equivalent`。
- 数值积分：控制周期 `0.02 s`，物理plant以 `0.002 s` 子步推进；道路Frenet坐标由 `s_ref_path/curvature_ref_path` 重建，并在端点增加20 m直线外推，避免载荷中心到终点时前后车辆越界造成假失败。
- 公平性：两方法使用相同plant、共同ICR分配、约束、控制时域12、每周期四车均求解、单次SQP和相同0.03 s求解时限；不再用旧 `safe_FK_step` 推进物理状态。
- 可重复性修正：初版按墙钟超时跳算会随机器负载改变动态结果，已改为固定调度；重复运行动态指标一致，仅墙钟耗时波动。
- 备份：`model/tf14_runtime.pre_coupled.py` 与 `model/tf14_runtime.pre_trace_sync.py`。
- SHA256：`adapter.py`=`1EBA013617301C94559BE584CC191E04ACA3743D2D9F699620922E52E049A07A`；更新后根运行器=`5E627F4F5250EF69DFBD38C06259EF1CDE7F3ED1E6A39F141CC89E01E7055307`。

### W0022｜C1正常通讯单移线对比

- 新增：`model/run_c1.py`、`run_c1_multi.py`；产物位于 `model/c1/`。
- 工况：横移3.5 m，路径长30.0431 m，曲率峰值0.0193073 1/m；seed 3201–3205在无随机激励的clean固定调度下是确定性重复，不应解释为5个独立统计样本。
- AKE-M：横向RMSE `0.06936 m`，连接力峰值 `383.72 N`，连接力RMS `161.94 N`，张开型内力P99 `53.11 N`。
- NR-KDCC：横向RMSE `0.02484 m`，连接力峰值 `362.33 N`，连接力RMS `86.46 N`，张开型内力P99 `24.81 N`。
- 相对变化：横向RMSE `-64.19%`，连接峰值 `-5.57%`，连接RMS `-46.61%`，张开P99 `-53.28%`；平均墙钟耗时约增加1%，仅作为当前硬件调度成本。
- 验收：两方法均完成、数值有限、作用反作用残差0、共同ICR残差约 `1e-14`，C1通过。
- SHA256：`run_c1.py`=`687FF0E9DD067CC15E4C85E70DAA9024E7AE03499B0501F0BEDD725369840FF1`；`run_c1_multi.py`=`A7FFA0D15BC9511CFE9D978296869234F886762207EADD9CBD6F6CAB303417FF`。

### W0023｜C2正常通讯回头弯对比

- 新增：`model/run_c2.py`；产物位于 `model/c2/`。
- 工况：使用项目原回头弯参考，3894个参考点，弧长83.5781 m，曲率峰值0.0838896 1/m，参考速度峰值1.04438 m/s。
- AKE-M：横向RMSE `0.18781 m`，连接力峰值 `3464.62 N`，张开型内力P99 `3072.98 N`，平均步墙钟76.41 ms。
- NR-KDCC：横向RMSE `0.12158 m`，连接力峰值 `1341.23 N`，张开型内力P99 `1130.49 N`，平均步墙钟95.71 ms。
- 相对变化：横向RMSE `-35.26%`，连接峰值 `-61.29%`，张开P99 `-63.21%`；NR-KDCC计算耗时更高。
- 验收：两方法均完成且数值有限，连接力低于当前仿真参考限值，共同ICR残差满足数值门，C2通过。
- SHA256：`run_c2.py`=`9CE6062D1D5D047BCF73417109FB5BC6F7CEBA8132A99F9AEDDEAEBD7E4644B4`。

### W0024｜C3通讯扰动/DoS停止门触发

- 网络一致性修正：原 `comm_restructure` 交付的是延迟/丢包状态，但NR质量矩阵曾从第二条隐藏随机信道采样；已改为直接使用每个实际交付链路的delay/drop事件，AKE-M与NR-KDCC冻结并重放同一公开前缀trace。
- 已执行：seed 3401的 `delay_loss`（1–3个控制周期延迟+10%丢包）、`dos_2s`（连续2 s全丢包）和 `dos_5s`（连续5 s全丢包）。
- delay_loss：NR相对AKE横向RMSE `-81.70%`，连接峰值 `+2.08%`，张开P99 `+45.66%`。
- dos_2s：NR相对AKE横向RMSE `-62.10%`，连接峰值 `+48.63%`，张开P99 `+71.05%`。
- dos_5s：NR相对AKE横向RMSE `-51.45%`，连接峰值 `+68.67%`，张开P99 `+1.95%`。
- 停止判据：预设的内部力保护门要求NR张开型内力P99不得比AKE-M恶化超过5%；`delay_loss`和`dos_2s`均失败，因此按用户要求停止，没有继续seed 3402–3403、Gilbert–Elliott方法对比、回头弯+DoS、执行器+网络联合扰动和C4统计包装。
- 边界：所有绝对连接力仍低于暂定12/15 kN仿真参考值；本次失败是相对“通讯保护”性能失败，不是材料撕裂或实物安全失效证据。
- 建议：把四点Fx/Fy、前后/左右张开代理和力变化率纳入NR预测代价/约束；将N1的AoI/序列拒收、本地降级、恢复滞环和软恢复正式接入主运行器；Pareto调参后先只复跑seed 3401的2 s DoS，过门后再恢复其余实验。
- 产物：`model/c3/report.json`、`compare.png`、`gate.png`、`stop.md`。
- SHA256：`run_c3.py`=`0698AD892DAB4811DB1165D93FE79EC9F431D80225D98C30BA1615151D79DC7C`；`finalize_c3.py`=`FCAD86E6467C2DCF1C4EF3AE10081BC63E1DC96EE88D0BDC4DC85B70B3017406`。

### W0025｜Koopman修正路线与审稿意见关闭盘点

- 用户要求：先处理Koopman/20步预测证据不足，考虑新方法或完整证明，并列出此前针对审稿意见已经完成的修改。
- 核查事实：当前C1/C2/C3实际控制时域均为12；没有20步滚动训练、1–20步预测曲线或12/20步闭环消融，因此已有clean改善不能归因于20步Koopman。
- 理论事实：实际31D模型的`||A+||₂=1.0980>r_u=0.998`，原式令`gamma=0`仍不可行；原sampled谱半径投影不能支撑连续输入域收缩和稳定性。
- 新增：`revision_2026/koopman.md`。
- 推荐候选：MF-IK（多步受力感知增量Koopman），在四车—货物误差状态上加入20步rollout、四点受力和守恒损失；通讯状态保持为外生调度/不确定性索引。
- 理论分支：只在误差子空间上尝试共同P/LMI或加权范数证书，显式处理不可行、回滚、冻结和fallback；若证书或闭环价值门失败，删除IRSP/双线性核心贡献。
- 文档同时把审稿意见分为“实质完成、部分完成、尚未解决”，避免把代码改动误报为论文意见已关闭。
- 本轮仅更新方案MD和工作记录，未修改控制代码、未启动新训练或实验。

### W0026｜K0–K1现行Koopman冻结、20步复算与停止

- 新增：`revision_2026/koopman/run_k0_k1.py`；只做诊断，不训练新网络、不写回控制器。SHA256=`338CFD791D84CD85637F4C5032D30AD74EFA2AFA0746F8CBAF6C98C4FCAF26D2`。
- K0冻结：对现行notebook、运行器、Koopman核心、矩阵helper、旧数据、参数和缓存E1逐文件记录SHA256；保存当前linear/bilinear/IRSP矩阵与输入采样域。
- 数据事实：旧数据为720条轨迹，576条训练、144条验证；144条验证轨迹参与网络开发/选择，不存在独立测试集；数据没有straight/单移线/回头弯场景标签，也没有网络元数据。
- 新划分已在训练前预注册到`k01/split.json`：新四车数据以整条轨迹为单位，按场景内`traj_id mod 20`作70/15/15 train/validation/test划分，外部失配集完全独立，窗口不得跨集合。
- K1实际模型复算：在现有144条验证轨迹中固定seed 42026抽取2048个20步窗口，比较实际DNN lift下的lifted linear、projected linear、bilinear和bilinear IRSP。
- 20步平均状态NRMSE：lifted linear `0.09594`；projected linear `0.12500`；bilinear `0.17239`；bilinear IRSP `0.19504`。因此当前双线性相对未投影lifted linear恶化约79.7%，IRSP恶化约103.3%。
- 旧缓存轻量筛选也给出相同方向：h20 L2为linear `1.2119`、bilinear `1.6743`、stable bilinear `1.6348`；该缓存不是实际DNN多种子训练证据。
- IRSP事实：投影后谱半径 `0.9920`、sampled有效谱半径上界约`0.9980`，但零输入矩阵二范数 `1.098003>0.998`；连续输入域范数门仍失败。
- 受力可辨识性反例：保持四辆车的全部旧观测与控制完全相同，仅改变旧状态未包含的货物纵向位置`0.012 m`，四个连接点分别由`0 N`变为约`300 N`。故旧6D单车Koopman状态不能唯一确定四点力，无法计算可信的1–20步受力预测误差。
- 停止门：`GK0_independent_test=false`、`GK1_scenario_stratification=false`、`GK1_force_prediction_error=false`，所以`continue_to_K2=false`。按用户要求停止，没有实现/训练MF-IK，也没有恢复C3/C4。
- 恢复条件：先用30维四车—货物plant生成带四点Fx/Fy、形变/速度、张开代理和力变化率的场景标注数据；在新合同上让raw linear和lifted linear都能输出独立测试集20步状态/受力误差，再进入MF-IK。
- 产物：`revision_2026/koopman/k01/report.json`、`split.json`、`files.json`、`matrices.npz`、`rollout.npz`、`state.png`、`diagnosis.png`、`stop.md`及`k01_run.log`。

### W0027｜Koopman变量集合变化实验细化

- 用户要求：把聊天中讨论的变量集合变化实验写入下一步Koopman计划，并结合既有力学、clean和C3结果完善顺序与验收。
- 修改：更新`revision_2026/koopman.md`，新增状态集合`S0–S7`和控制输入集合`U0–U3`。
- 因果顺序：先固定线性结构比较阵列聚合、四车独立、连接形变、显式力输入/受力监督；冻结状态合同后再比较linear、one-step bilinear、20-step bilinear与MF-IK；最后比较网络变量入lift和外生调度。
- 推荐合同：`S5-force-out + U1-four`，即四车/货物/连接器形变为物理状态，四点力/张开/力变化率为多任务输出，四车实际施加输入作为控制输入；是否最终采用须由独立test决定。
- 公平性：按整条轨迹/场景/seed划分，固定lift容量并补参数量匹配敏感性，使用因果力变化率和teacher-free 20步rollout，禁止未来信息与相邻窗口泄漏。
- 既有结果约束：K0–K1已证明旧数据无独立test/场景标签、旧状态对四点力不可辨识、现行bilinear/IRSP的20步NRMSE劣于linear；因此先生成新四车数据并建立linear受力预测基线，再做变量与模型消融。
- 验收：变量扩维本身必须产生独立test和闭环收益；若显式力输入只降低训练误差，优先更紧凑的受力监督输出；网络变量默认外生，只有跨分布证据充分才进入lift。
- 本轮仅修改计划MD和工作记录，未修改代码、未生成新数据或启动训练。

### W0028｜多专家平滑门控纳入Koopman计划

- 用户补充主线讨论：不同工况不是状态维度变化，而是有效变量集合/敏感度变化；建议完整状态上的纵向、转弯、过渡三专家平滑门控，并以Jacobian敏感度验证活跃子空间。
- 修改：更新`revision_2026/koopman.md`，新增G-MF-IK候选、E-L/E-C/E-T专家、物理工况门控`rho_phys`、网络可靠性`rho_net`、soft gate、变量组稀疏、MPC递归门控和共同P证书边界。
- 结构决策：所有专家共享完整状态、lift和decoder；推荐“共享基模型+门控专家残差”，变量组门控只调整专家残差贡献，不直接删除状态。
- 因果边界：网络丢包不是物理工况，缺失观测使用`value+mask+AoI`；网络变量默认作为观测置信度/外生调度，不混入物理lift。
- 风险控制：当前bilinear 20步误差明显劣于linear，因此先验证三线性专家；只有soft-gated linear通过独立test后才允许构造G-MF-IK。
- 验证：增加oracle、hard switch、soft gate、group-sparse、noTransition、frozenGate消融；比较分工况1–20步误差、四点力/张开、门控抖振、专家塌缩、plant Jacobian一致性和实时开销。
- 理论：共同P只能给出共享误差子空间凸组合的点态收缩；完整闭环仍须处理bilinear输入盒、残差、门控误差/滤波状态、观测缺失、终端集与fallback，不能从专家LMI直接跳到闭环稳定。
- 本轮仅完善计划MD和工作记录，未修改模型代码或启动训练。

### W0029｜K2.0四车—货物Koopman新数据

- 新增：`revision_2026/koopman/generate_k2.py`，从已验收的30维四车—货物plant、共同ICR转向分配和四点连接模型生成K2数据。
- 首次烟测发现标为`staged_100m`的轨迹在36 s只到`87.86 m`；加入`distance_gate_passed`硬门后，60 s烟测在`98.856 m`停止，证明停止门有效。最终把90 s设为安全上限，轨迹仍在首次达到100 m时立即结束；第三次烟测6/6通过。
- 完整数据：120/120条；train/validation/test/external=`70/15/15/20`，五类场景各24条。基础场景内按整条轨迹`traj_id mod 20`冻结为14/3/3，external从不参与归一化或调参。
- 状态/输入合同：S1/S2/S3/S4维数=`12/30/46/64`，受力输出18维；U0/U1/U2/U3维数=`2/8/8/13`。力变化率使用因果差分，窗口不得跨轨迹。
- 完整集最大连接力`2672.43 N`，最大张开代理`791.72 N`，共同ICR残差峰值`1.48e-14 m/s`；全部数值有限，没有删除异常轨迹。数值只用于当前仿真门，不解释为实物材料阈值。
- SHA256：`generate_k2.py`=`ACE7016564818781C7206403A95B2AABBCEAB9E8CB815E5F09256408FFBA0390`。
- 产物：`revision_2026/koopman/k2/data_full/manifest.json`、`split.json`、120个带hash的轨迹文件及`full.log`。

### W0030｜K2.1–K2.3线性基线、变量与输入消融

- 新增：`revision_2026/koopman/linear.py`；训练统计只来自train，独立test/external均做1–20步teacher-free rollout，逐轨迹bootstrap 2000次。
- K2.1通过：S3+U1 raw linear在test的10–20步状态/连接力/张开NRMSE=`0.03710/0.21580/0.43825`；lifted linear=`0.03112/0.20216/0.40668`，两者test/external均有限。
- K2.2通过：S2相对S1至少一项门通过；S3相对S2的连接力差值95% CI=`[-0.4713,-0.1650]`，张开差值95% CI=`[-0.3715,-0.1773]`，支持保留连接点形变和相对速度。
- S4相对S3的test连接力/张开NRMSE相对改善=`20.74%/5.58%`，在线性专家阶段暂用S4。边界：固定非训练lift下，S5与S3使用相同输入和受力监督读出，不能伪造为独立消融；真正S4/S5比较仍需共享可训练lift。
- K2.3完成：U0相对U1显著恶化状态和连接力；U2也较U1差；U3改善状态但张开CI跨0。后续物理输入仍固定U1，不把命令输入与实际输入混称公平优越。
- SHA256：`linear.py`=`8B0DD1FD2754C3FB34E1B825FC8A5394DAD03CF3449CEB977A65D3F62670E540`。
- 产物：`revision_2026/koopman/k2/linear/results.json`、`report.md`、7张误差曲线与模型矩阵。

### W0031｜K2.9–K2.10三线性专家失败并停止

- 新增：`revision_2026/koopman/experts.py`；E-L/E-C/E-T共享S4 fixed lift、U1输入和decoder。hard/soft只使用预测当前状态/受力、当前或计划输入及后向差分；弱标签oracle读取test物理标签但不可部署，也不是数学误差上界。
- 训练标签数E-L/E-C/E-T=`66017/44086/9142`；validation选择`tau=0.15`、平滑系数0。test软门平均占用=`0.5563/0.3582/0.0856`，有效专家数`1.123`，接近hard switch。
- 固定global linear的test 10–20步状态/连接力/张开NRMSE=`0.02702/0.16024/0.38398`；soft gate=`0.02919/0.16567/0.35952`。
- 分层：soft相对global在E-L/E-C分别恶化`35.61%/17.16%`，只在E-T改善`18.16%`；不满足至少两层改善、第三层恶化不超过5%的门。
- 配对证据：soft减global的连接力NRMSE均值差`+0.02462`，95% CI=`[+0.01128,+0.03630]`，方向明确更差。external的状态/连接力/张开三项也全部恶化。
- 局部事实：soft相对noTransition在E-T过渡段综合误差、连接力p95和张开p95分别改善`53.11%/60.33%/58.28%`，说明E-T有局部价值，但不能覆盖总体与外推失败。
- 停止：GK2线性专家门失败；没有继续变量稀疏/Jacobian包装、bilinear、MF-IK、IRSP、稳定性证书或闭环实验。
- 解决方案：新增`revision_2026/koopman/k2/solutions.md`，优先采用单一linear AKE降级路线；备选为只保留共享global+受限E-T残差、因果低通及真正共享可训练lift的S4/S5确认实验。
- SHA256：初次执行证据脚本`experts.py`=`7C462758BAC20E668CA955049862FD2CE530D6029EE7721AD62A2C4C44D3A274`；最终脚本=`7D1D58C85AB34A4E84E8CE4E411BFC3BB84E69528A3C165AA3DE721F429F86F9`，差异仅修正文档措辞“oracle不是数学上界”，不改变计算。
- 产物：`revision_2026/koopman/k2/experts/results.json`、`stop.md`、`state.png`、`connector.png`、`opening.png`、模型矩阵和运行日志。

### W0032｜K3.0证据隔离与确认集预注册

- 最新方案切换：`koopman.md`新增K2失败状态并指向`revision_2026/koopman/k3.md`；不重复三完整专家，也不恢复bilinear/MF-IK/IRSP。
- 新增：`revision_2026/koopman/freeze_k3.py`，冻结K2方案、脚本、solutions、数据manifest、线性/专家结果及stop文件hash，并逐个复核120个K2轨迹hash。
- 证据降级：旧`test=15`和`external=20`已在`development_split.json`逻辑映射为`dev_test_old/dev_external_old`；原文件与K2 manifest不被改写。
- 确认集预注册：训练前冻结`confirm_internal=100`（五场景各20）和`confirm_external=40`（五场景各8）的seed及精确参数组合；确认集只允许在G34候选冻结后生成。
- external冻结因素：货物质量、车辆横摆惯量、连接刚度/阻尼/间隙、附着和曲率。当前plant的货物惯量由质量和几何派生，故没有伪称独立扫描货物惯量；独立惯量失配施加在车辆横摆惯量。
- 训练协议冻结：S4/S5总lift维数96、隐藏宽度64、SiLU、U1输入、五个模型seed、20步teacher-free、相同损失/学习率搜索预算；方案B残差范数上限网格固定为全局A范数的1/2/5/10%。
- G30初检和只读文件二次审计均通过：120个K2轨迹hash一致，development计数`70/15/15/20`，config/development/confirm规范化hash全部一致。
- 产物：`revision_2026/koopman/k3/config.json`、`freeze.json`、`development_split.json`、`confirm_preregistered.json`、`g30.json`及`k3_g30.log`。

### W0033｜K3.1共享可训练lift与G31数值门

- 新增：`revision_2026/koopman/lift.py`、`transition.py`、`run_k3.py`。S4/S5统一总lift维数96、隐藏宽度64、SiLU、U1输入和18维共同受力decoder；30维四车—货物状态由lift前30维直通解码。
- 首版G31只给S4提供64维力状态，虽通过有限性门但不满足`k3.md`的`value+mask+AoI`压力测试路径；在五seed训练前主动废止该实现并重新运行G31。最终S4读取64维物理量+四点mask+四点AoI共72维；S5只读取46维S3。
- 字段级计算图审计确认S5不存在四点力、Q或力变化率输入路径；S4 clean输入明确使用`mask=1/AoI=0`，后续缺测压力可在同一计算图中输入mask/AoI。
- 最终参数量：S4=`17962`、S5=`17988`，相对差`0.1445%`，低于冻结的2%门；差异来自合法前向编码器结构，而非占位参数。
- 数值冒烟：两模型经3次梯度更新后的20步teacher-free rollout均有限；S4/S5物理状态直通重构峰值均为0。
- 物理构造：同一预测连接力以正负号作用于货物/车辆，作用—反作用残差峰值为`0 N`。该恒等残差来自结构约束，不作为模型精度改善证据。
- G31通过。边界：三次更新只用于反向传播和有限性检查，不能解读为可训练lift优于fixed linear。
- SHA256：`transition.py`=`1E171E318617663BF2173B1F8172EB4AD23F8D1C337059355383CF52C1D079AA`；最终`lift.py`=`7581413CE04FFDBAFAA886327718F42698417BBC3FB86735FCA96D56CC79D262`；当前`run_k3.py`=`3A97FC9BBE79D463AC7A1308DA1CE73FE06768A0B5A3E3B878564BAF7A10CEFD`。
- 产物：`revision_2026/koopman/k3/g31.json`、`g31.log`、训练集normalizer及两份G31 checkpoint。

### W0034｜K3.2 A-S4/A-S5五seed训练与G32停止

- 执行：S4/S5分别用冻结的4组超参数预算在validation选参；两者均选择`lr=0.001`、`lambda_H=1.0`的第2组。旧test/external未参与选参，只以`dev_test_old/dev_external_old`在模型冻结后评价。
- 五seed：`73101–73105`全部运行并恢复各自validation最佳checkpoint，没有只报告最佳网络seed。S4最佳validation综合分数=`0.22595/0.23661/0.22489/0.23400/0.23819`；S5=`0.22048/0.21957/0.22006/0.22206/0.23987`。
- 训练成本：8次选参训练加8次其余seed训练的唯一训练墙钟合计`742.60 s`（约12.38 min，不含数据载入和最终压力评价）；每轮历史和checkpoint hash均保留。
- dev 10–20步NRMSE：A-S4状态/连接力/张开=`0.08201/0.20442/0.39365`，综合=`0.22669`；A-S5=`0.07563/0.20247/0.40204`，综合=`0.22671`。
- fixed对照：K2 fixed S4综合=`0.19041`，K2 fixed S3/S5-operational综合=`0.21332`；两种trainable lift均不优于各自fixed linear，触发G32停止条款。
- S4减S5逐轨迹差：状态`+0.00548`，95% CI=`[+0.00347,+0.00774]`，明确更差；连接力CI=`[-0.00893,+0.00031]`跨0；张开CI=`[-0.02483,-0.00356]`但相对改善仅`2.09%`，未达到S4所需10%。
- external综合：S4/S5=`0.29925/0.31803`，S5无external优势；S4也未形成满足10%+CI的主指标优势，故两种合同均未被选择。
- S4压力：2%噪声/bias影响小；AoI 1/2/4周期使状态分别恶化`22.11%/66.65%/179.43%`、连接力恶化`27.83%/80.33%/199.80%`、张开恶化`16.94%/52.39%/141.06%`。单点`value+mask+AoI`优于直接置零，但仍使状态/连接力/张开恶化`14.43%/13.45%/5.15%`，传感压力门失败。
- G32结论：`return_to_old_fixed_linear`。按`k3.md`停止；没有训练方案B、没有生成confirm、没有接入MPC/DoS/时域消融，也没有恢复三专家、bilinear、MF-IK或IRSP。
- 新增解决方案：`revision_2026/koopman/k3/solutions.md`，区分“当前回到fixed linear”与“若以后重启须新预注册缺测增强/外生可靠性输入”的新研究分支。
- SHA256：最终`run_k3.py`=`566AF723248E7FC3371E03AB4BC3B89A1B040AC13419CD0950A23280C7A66331`；`A_results.json`=`06DD7B1B608EEB81839ABEA9941AB12B832E51BF9A352A9E1A7C00696CAB0D19`；`k3/solutions.md`=`4711AEBA69C0E0088A92EF691795457AE84FDEB81F85D8CC10A83F92305F4FFB`。
- 产物：`revision_2026/koopman/k3/development/A_results.json`、`search_A.json`、三张20步曲线、全部checkpoint、`k3/stop.md`和`k3/solutions.md`。

### W0032｜方案C主线与A/B统一对照实验书

- 用户要求：查看最新`k2/solutions.md`，实行方案C，同时在同一过程中实现方案A和B并比较差异，先形成详细实验MD。
- 核查事实：最新方案A是单一全局lifted linear；方案B是共享全局模型加E-T小残差；方案C是共享可训练lift下S4-force-in与S5-force-out的真实状态合同比较。C与A/B不是同层级算法。
- 设计修正：采用`state_contract(S4/S5) × transition_residual(A/B)`二因素矩阵，训练`A-S4/A-S5/B-S4/B-S5`，分别估计状态合同效应、过渡残差效应和交互效应。
- 新增：本地`D:\PDxc\Review\k3.md`，远端目标`revision_2026/koopman/k3.md`；并在`koopman.md`增加执行书入口及K2三专家失败状态。
- 数据边界：现有15条test和20条external已经被查看，降级为development；模型/门限冻结后新增每类至少20条的confirm_internal和独立confirm_external。
- 方案C：共享物理状态直通lift、同构decoder、同20步/force/physics loss与匹配参数量；S4读取显式力，S5只把力作为多任务输出；S4增加噪声、bias、mask和AoI压力测试。
- 方案B：只增加因果门控的小E-T线性残差，预注册残差范数上限、低通和门控网格；不恢复三完整专家、bilinear、MF-IK或IRSP。
- 停止门：离线确认集、external、闭环受力和实时性逐级验收；B失败即采用A，S4/S5无可靠差异优先部署假设更弱的S5，二者不优于旧fixed lift则回退旧方案A。
- 本轮仅新增/更新实验计划MD和工作记录，未修改模型代码、未生成确认数据或启动训练。

### W0035｜依据K3最新负结果重设计K4实验

- 用户要求：根据最新实验结果重新设计实验。
- 核查依据：读取5080上的`k3/development/A_results.json`、`k3/stop.md`和`k3/solutions.md`。K3的A-S4/A-S5五seed综合NRMSE=`0.22669/0.22671`，均劣于对应fixed基线`0.19041/0.21332`；S4相对S5仅张开改善`2.09%`，状态恶化`8.43%`；AoI 1/2/4周期下trainable S4状态误差恶化`22.11%/66.65%/179.43%`。
- 独立判断：不继续端到端共享lift、三完整专家、E-T方案B、bilinear、MF-IK或IRSP。K3保留为已执行失败记录，不事后改写停止门。
- 新增：`revision_2026/koopman/k4.md`。新主线为fixed S4/S5传感压力选择、固定lift上的低秩小范数20步锚定修正、一次性confirm、再按“通讯致因→clean单移线→clean回头弯→网络攻击”进入闭环。
- 新门：G40证据隔离、G41 S4/S5部署、G42开发、G43独立确认、G44闭环/实时性。任一关键门失败立即回到fixed linear，不生成后续证据。
- 更新：`revision_2026/koopman.md`的最新结论、状态说明、专项任务树、近期执行顺序和当前执行书入口；旧MF-IK/专家内容标记为历史候选或失败依据。
- 数据边界：旧test/external继续降级为development；K3预注册confirm尚未生成，只允许在K4候选、网络trace和全部阈值冻结后一次性使用。
- 本轮只修改实验计划和工作记录，未修改模型/控制代码，未生成confirm，未启动训练或闭环实验。
- SHA256：`k4.md`=`C2640971370EFC346F5EEC0F1542AA318E12BE1BA84BA62406F3479777738B12`；`koopman.md`=`5FCC7E339B1560BEB6D11CE4B84A4DA89D486883F94E1096628A829394B0E40B`。

### W0036｜K4协议小修、G40冻结与fixed S4/S5压力实验

- 核对结论：K4没有绕过K3的G32失败；继续禁止trainable lift、三完整专家、bilinear、MF-IK和IRSP。确认集仍未生成，可继续development阶段。
- 协议小修：低秩修正采用单侧零/单侧正交初始化以避免双零因子零梯度；滚动起点20步压力只作用四点力消息；张开/力变化率由处理后的力因果重算；W2固定使用上一时刻M1-S5单步预测；G41/G42改为可复算数值门，并冻结K4.2优化预算。
- G40=`True`：120条轨迹hash、70/15/15/20角色、K2/K3证据和140条confirm预注册行通过二次只读核验；confirm轨迹文件=0，未查看confirm。
- fixed复算：M0/M1/M1F相对K2已保存1–20步指标最大绝对差=`0.000e+00`，门限=`1e-10`。
- validation clean S4/S5综合NRMSE=`0.18526194/0.20804246`，S4相对改善=`10.95%`。
- G41=`True`；K4.2唯一合同=`S4+S5-supervisor`。具体轻压力差值与paired CI见`koopman/k4/development/sensor_stress.json`。
- 本轮没有生成confirm、没有训练M2/M3、没有接入MPC/DoS闭环；旧test/external只标记为dev_test_old/dev_external_old。
- SHA256：
  - `koopman.md` = `B502D8F66371875EE20CDD0C2E78A17857F8F8DBCA22CEEC91504E9EAED1BF19`
  - `koopman\k4.md` = `E5CE84F30D1857F5EEA0C6EADE8C19CF93F031B99BA84F018A711ABEABA4DD00`
  - `koopman\run_k4.py` = `14AE10B77FDDC8E498A199CC8C3B4E0AB47F916C49E6B88086CBFD5E31478907`
  - `koopman\k4\config.json` = `0DFC1DF6339792B45716C806097807724B97824A443A7ECFDCA21CFED1280DE3`
  - `koopman\k4\freeze.json` = `2EF3C7D77F6A99CB5A657788CD292174FA57D6517292F23CEBA2CBCD26046D95`
  - `koopman\k4\development\fixed_recalculation.json` = `A7E97136D5055101714A6D2AF5795604E767DDF5A21439E24D79AE2F424EEEEF`
  - `koopman\k4\development\supervisor_search.json` = `5749B3052AE194F9AB4715BEADC177F2854AEC687DE98C0227187E058FF031A1`
  - `koopman\k4\development\sensor_stress.json` = `89663AA0ECB4E79D085F209FAAA86D5ADE49B2501AF1F45CF8184F67831F6E9C`
  - `koopman\k4\development\sensor_stress.png` = `650C642F511B6782E09F448AAA842A7FF5C833E64CE249366468664DD9AFA2B2`
  - `koopman\k4\development\switch_timeline.json` = `87E592FB765FFAE81EBE1383E3FC354CFB671DFF1503B656643143E62E11D474`
  - `koopman\k4\development\switch_timeline.png` = `62DE31354AE103AFAB27EC29B9681D149972F9051C2D841610B1EAD3E4F553FC`
  - `koopman\k4\report.md` = `0FE247BCDD8F79CA9986E8C8487F8F3D6491E27B13516E42ED11B56D98CBBDC9`

### W0037｜修正G41切换漏判并回退S5合同

- 修正原因：首次自动结果把G41标为通过，但脚本只记录切换次数，漏掉了计划中“不能通过高频切换换误差”的布尔裁决；该结论不可接受。
- 协议澄清：轻压力下最短驻留固定为至少5个控制周期、总切换率不超过0.5 Hz；因为已看到首次结果，本轮不再重调W4网格，违反即保守回退S5。
- G40=`True`：120条轨迹hash、70/15/15/20角色、K2/K3证据和140条confirm预注册行通过二次只读核验；confirm轨迹文件=0，未查看confirm。
- fixed复算：M0/M1/M1F相对K2已保存1–20步指标最大绝对差=`0.000e+00`，门限=`1e-10`。
- validation clean S4/S5综合NRMSE=`0.18526194/0.20804246`，S4相对改善=`10.95%`。
- G41=`False`；K4.2唯一合同=`S5-operational`。具体轻压力差值、paired CI和切换率见`koopman/k4/development/sensor_stress.json`。
- 本轮没有生成confirm、没有训练M2/M3、没有接入MPC/DoS闭环；旧test/external只标记为dev_test_old/dev_external_old。
- SHA256：
  - `koopman.md` = `995D1D25BA567AECAB04B7625C027D18F0E016C4C1065F73970AC24821126F7F`
  - `koopman\k4.md` = `68DEF3F915D60001EE8FA475EA4DA4AF6376BDF812C226234C46B1B518AE6A39`
  - `koopman\run_k4.py` = `30B77516FA69DE5228CCB8460199F995C69BD49AECF5E68FBF6261843C354DCC`
  - `koopman\k4\config.json` = `AD49C3379E7436B25E485A0215A613691179840D47DEE5F8DA500A513D7F54A2`
  - `koopman\k4\freeze.json` = `6D30001C941F17E5F15683059C3FB862F93482D9601D1106B0FAC93A858ED65B`
  - `koopman\k4\development\fixed_recalculation.json` = `D3178D9AEC3AF814981742BF90F0443915615BD7BCCEEC24CB6026EA4E04B7EB`
  - `koopman\k4\development\supervisor_search.json` = `9697C012104A4525FC4C23EB2C686FF1641AA63B02BC898B71010F3C84B13323`
  - `koopman\k4\development\sensor_stress.json` = `406C78CE569E81C15A4EC760E6AF35B289CF2948DF2CE5BA1D469263C2DB38FA`
  - `koopman\k4\development\sensor_stress.png` = `650C642F511B6782E09F448AAA842A7FF5C833E64CE249366468664DD9AFA2B2`
  - `koopman\k4\development\switch_timeline.json` = `87E592FB765FFAE81EBE1383E3FC354CFB671DFF1503B656643143E62E11D474`
  - `koopman\k4\development\switch_timeline.png` = `62DE31354AE103AFAB27EC29B9681D149972F9051C2D841610B1EAD3E4F553FC`
  - `koopman\k4\report.md` = `2225D1C851F0FD59E53178AB9880F1E02D1D0B882852A3AAD333B454C1645D87`

### W0038｜K4.2 S5固定lift多步修正开发门

- 前置：修正版G41失败，S4+S5 supervisor因随机丢包下逐包抖振被关闭；K4.2唯一合同为S5-operational。
- 实验：固定K2二次lift和U1-four，比较M1 fixed、M2全量20步refit和M3低秩小范数锚定修正；M3只搜索预注册的3个rank×3个范数上限，随后M2/M3各五seed。
- validation M1/M2/M3综合NRMSE=`0.20804246/0.24519640/0.19357813`。
- dev_test_old M1/M2/M3综合NRMSE=`0.21332058/0.25044592/0.19802767`。
- G42=`False`，决策=`stop_return_to_M1_fixed_S5`；confirm生成/查看均为false。
- 本阶段没有生成确认集、没有接入MPC或闭环，也没有恢复trainable lift、三专家、bilinear、MF-IK或IRSP。
- SHA256：
  - `koopman\train_k4.py` = `C5CA8D9EDB1B97E1259EA2EC24E4C62BF71E26E64FC132B1355F32BAF7284032`
  - `koopman\k4\development\k42_freeze.json` = `64EF274E1E06B7F1620C2AC8E4069ED5E6100D09E7ADF827BDD19AFA2F5498CE`
  - `koopman\k4\development\k42_results.json` = `8C2E35C39FDC675C7F3172A9E03610C12C1D556714DCAE59A1CB037B653ADF19`
  - `koopman\k4\development\horizon_state.png` = `F77C8C0B9C65862AC65DD706385EF7FD735C0ADF1BFED9C2B8A0275483DC3D29`
  - `koopman\k4\development\horizon_force.png` = `489EC3488F921DB9AA7EF01EBA306722C7E0F0FC06D7C2326C6B2D86C45D7D68`
  - `koopman\k4\stop.md` = `8463385D206CDF1D9AF2B0ED33CB81EC1BBA84AC7A9B7E1BA4874EE856B6A2BE`
  - `koopman\k4\solutions.md` = `0B972695394F48EF0BD5CC5B4382EF28FFC5AB5A543B8F4CE9942E28285E8865`

### W0039｜K4最终只读复核

- 代码留痕补全：`run_k4.py`仅增加`train_k4.py`为G40必检冻结文件；没有改变K4.1压力算法或已冻结阈值。最终SHA256=`5CABC5916092FAD22EB1F897AE28276BDE2A6DEBDF989D4E0C0511A387DB91D0`。
- 最终协议hash：`koopman.md`=`995D1D25BA567AECAB04B7625C027D18F0E016C4C1065F73970AC24821126F7F`；`koopman/k4.md`=`68DEF3F915D60001EE8FA475EA4DA4AF6376BDF812C226234C46B1B518AE6A39`。
- 最终冻结hash：`koopman/k4/freeze.json`=`792D5A974AE75E88453FE8388CA4E935C4A770186434B04EBA184D9DC73BE570`；`koopman/k4/development/k42_freeze.json`=`64EF274E1E06B7F1620C2AC8E4069ED5E6100D09E7ADF827BDD19AFA2F5498CE`。
- 最终结果hash：`koopman/k4/development/k42_results.json`=`8C2E35C39FDC675C7F3172A9E03610C12C1D556714DCAE59A1CB037B653ADF19`。
- 确认集复核：`confirm`相关NPZ文件=`0`，K4确认目录=`0`；G42失败后没有生成/查看确认集，没有启动K4.3、闭环或更强网络攻击。
- 最终允许动作：论文与后续控制实验只可采用M1 fixed S5-operational作为Koopman predictor；本轮M3只保留为“受力改善但状态退化”的开发负结果。

### W0040｜统一“货物拉伸载荷”术语并按K4最终数据更新MD

- 用户要求：把`opening`改成更直白、学术的中文表述，并根据最新数据更新MD。
- 术语决定：历史代码/JSON字段`opening`继续保留以保证脚本、checkpoint和结果兼容；中文正文统一称为“货物拉伸载荷”。`Q_FR`称“前后向货物拉伸载荷”，`Q_LR`称“左右向货物拉伸载荷”。明确它是单位N的差动力代理，不是连接器张开距离、货物裂缝宽度或材料撕裂概率。
- 最新事实：G40通过；confirm生成/查看均为false。G41中fixed S4 clean相对S5改善`10.95%`，但supervisor违反最短驻留/`0.5 Hz`切换率门，因此回退`S5-operational`。
- K4.2分项：M1/M2/M3 validation综合NRMSE=`0.20804246/0.24519640/0.19357813`；M3相对M1综合改善`6.95%`，状态恶化`21.70%`，连接力改善`10.05%`，货物拉伸载荷改善`7.63%`。5/5 seed方向一致且全部H=20有限，但G42仍因综合改善不足8%和状态恶化超过5%而失败。
- 更新：`revision_2026/koopman/k4.md`增加术语公式、K4.0–K4.2最终结果表、停止结论和已完成任务树；`revision_2026/koopman.md`更新总判断、术语、任务状态和后续允许动作；`revision_2026/koopman/k4/report.md`扩展为完整最终报告。
- 边界：没有修改代码/JSON字段、模型、阈值或结果；没有生成confirm，没有启动MPC、闭环或更强网络攻击。最终预测器仍为`M1 fixed S5-operational`。
- SHA256：`koopman/k4.md`=`0D67F0443AF3E95FA4EAEAED7860932463BF7E2828A0CC8E5ED76447C5C374B3`；`koopman.md`=`E146878B44E14B87CBC7656B434C002919F6AE9CF38C844AEBAC65567B267A1C`；`koopman/k4/report.md`=`F1E05FD6FE35344945B239617FD45B2727270E9D58C5018BA8AB2706537B5E1B`。

### W0041｜预注册N2固定S5受力优先通信保护

- 最新MD核对：K4/M3、confirm与K4闭环仍被G42停止；允许的下一步只能在`M1 fixed S5-operational`上独立研究四点受力约束、AoI降级和恢复冲击。
- 代码事实：旧`run_comm.py/run_protect.py`使用手写匀速外推，C1–C3使用旧TF14预测器；此前没有代码真正加载`M1 fixed S5-operational`。因此没有直接重跑旧脚本。
- 旧N1审计：其原门判定为通过，但heavy通信下连接力P99相对无保护增加`41.18%`；这不满足最新版“先看受力”的目标，N1降为待改进基线。
- 新增预注册书：`revision_2026/model/n2.md`。固定smoke seed 3199、证据seed 3101–3105、clean/medium/heavy顺序、同trace门、N1历史复现门、受力/载荷/跟踪/恢复冲击门和失败停止规则。
- 新增代码：`revision_2026/model/run_n2.py`。只读加载hash固定的`S3-U1-lifted.npz`及归一化器，重建46维S3状态，以5步预测选择共同ICR控制blend，并记录四点Fx/Fy方向、`Q_FR/Q_LR`、四车/货物/系统横摆、AoI、滤波比例与恢复冲击。
- 设计包络：预测连接力3000 N、货物拉伸载荷1200 N；二者只是控制设计限制，不是材料撕裂认证阈值。
- 本条记录生成时尚未运行smoke或证据seed；不得依据后续3101–3105结果回改本轮门和阈值。
- 预运行SHA256：`model/run_n2.py`=`9F939B675449CC3FADEE892A842FB4384D4263164BFCC052263EC1A749DB40D2`；`model/n2.md`=`7226D19353EE6BE3433E1EEAA79D702F6524DF5C68512BE0F9AE54DD1CCC9220`。

### W0042｜N2代码smoke通过

- 命令：`E:\anaconda\envs\pytorch_new\python.exe revision_2026\model\run_n2.py --smoke`。
- smoke专用seed=`3199`；只运行clean/heavy的N1/N2接线检查，不用于性能选型或阈值调整。
- 结果：模型hash、归一化器hash、clean同trace、heavy同trace、clean透明性、全部完成且有限，六项均为`true`；smoke总门=`PASS`。
- 决策：不改任何预注册阈值，允许进入3101–3105的N2.1五seed配对验收。
- SHA256：`model/n2/smoke.json`=`43F1CF25980D8813B29122F10E1DD76A56B996C62CB6AFB3A40219F2CF1F79A4`；`model/n2/heavy_dynamics.png`=`2FF9FDC6BBE241BD5ED744755118BB327A748AC0B9BBB1A312ECD9E992D0C1B4`；`model/n2/smoke_heavy.npz`=`8AF4A5AB5DABB461E6F5725685F0977F125DEA2D34969CF46B179821C6248381`。

### W0043｜N2.1五seed受力优先门失败并停止

- 命令：`E:\anaconda\envs\pytorch_new\python.exe revision_2026\model\run_n2.py --full`；固定seed=`3101–3105`，固定工况=`clean/medium/heavy`，方法=`N1/N2`。
- 可复现性：所有方法/工况trace SHA256逐对相同；N1相对历史`protect.json`关键均值最大绝对差=`1.3132e-13`；clean下N2完全透明；全部30次运行完成、有限、内力平衡残差为0，绝对连接力低于暂定12 kN。
- medium相对N1：货物位置RMSE`+32.19%`，连接力P99`-15.79%`，货物拉伸载荷P99`-10.74%`，连接力变化率P99`-27.83%`。
- heavy相对N1：货物位置RMSE`+63.42%`，连接力P99`-5.63%`，货物拉伸载荷P99`+48.95%`，连接力变化率P99`-17.89%`。
- 失败门：heavy货物拉伸载荷非劣5%、heavy跟踪非劣10%、heavy连接力或拉伸载荷至少改善10%。N2总门=`FAIL`。
- 因果判断：每车基于自己的延迟视图预测一套四车联合控制，但只执行本车一行，四车最终控制并不是任一S5已评估的联合方案；固定S5能压低部分连接力范数，却不能给`Q_FR/Q_LR`与跟踪提供联合闭环保证。
- 结果审计：N2 heavy的恢复跳变记录为0，是因为该trace中没有形成可辨识的保护退出恢复事件，不能解释为恢复冲击改善。代码已增加`recovery_event_count`和“双方法均观测到恢复”门；这是防止假通过的审计小修，未重跑/改写本轮已冻结结果。
- 停止决定：不启动单移线、回头弯或DoS扩展；不在3101–3105上继续调阈值。已更新`model/n2.md`执行后附录和`model/n2/solutions.md`。
- 执行结果SHA256：`model/n2/report.json`=`45D2A2EE169C9CDADBD6BAEFDED1C5F8436F656EE9722BBCF8C097E0DC74C63C`；初始`compare.png`=`194AD2449F3F1AF21840CF15292D964AB2496934AB0AE12C7CF2EBECD106E1CC`；`heavy_dynamics.png`=`7F14A4815E8279FB521ACDEAAE3ABD79C1EF9BD4C07CF320698B115C3BCCA232`；`heavy_seed3101_n1.npz`=`6475B692479C1B6D9048DDC1D7C71C2F7C0E736D816561923077DA97F4792E5E`；`heavy_seed3101_n2.npz`=`438AF07B8DCC64751484B17F6D00317004889223E293B8FF5DE5590A873BF4AB`。
- 可视化审计：初始比较图把“未观测恢复事件”的0值画成`-100%`，容易误读为恢复冲击改善；未改数值报告，仅从比较图删除该柱并注明不可辨识。审计重绘`compare.png` SHA256=`5E0900B7BD2BC061C5DBC98AB823C5859442680462024B24603B40BB810CDD31`。
- 执行后文件SHA256：`model/run_n2.py`=`2C304B03C2121CBF6137E1B6777F431FD8ABADDE9E25D75FBFDBB781B15812BD`；`model/n2.md`=`F4EACF30B23A27AE33FF03BE9AF897B7311C82D65EA1C037942E7AC1E060C62A`；`model/n2/solutions.md`=`679B9F9C8AA0ED5ADA3B6D7A3AC547D02B93B31187EF6AECA40446E6B912A8DB`。

### W0044｜细化Koopman方法场景对比协议并完成训练前只读审计

- 用户授权：细化`D:\PDxc\Review\koopman_compare.md`并在5080完整执行，不扩展原K0–K6、E0–E9范围，运行问题就地解决，最终给出各方向优劣。
- 前提纠正：固定lift含`z0=1`；若K2同时含`Bu`与完整`u_j z`，则`u_j z0`与`Bu`完全重复，回归矩阵必然秩亏。协议改为bilinear项只作用`z[1:]`，独立列数`837`，转移参数`77,841`。
- 执行细化：冻结E0–E9标签算法、K3五个物理输入模态、`r={2,4,8,12}`、参数匹配`r=2`、ridge网格、K4/K5结构与seed、K6 oracle门、学习曲线seed、E9/confirm/闭环seed和幂等阶段命令。没有增加新模型、指标或攻击场景。
- confirm可实现性修正：生成前冻结seed、生成器/config/model hash；轨迹内容hash在每条文件生成后、任何指标读取前写manifest并二次校验。不能声称在文件生成前已知道其内容hash。
- 只读T1审计对象：冻结manifest `B3DED2AC...455CE`、现有70条train，共`119,245` transitions。8维U1有效秩`8/8`、有效条件数`150.23`。
- 去重后的full bilinear：有效秩`827/837=98.81%`，有效条件数`9.4905e7`，低于原`1e8`门但仅有约5.1%余量，结论为“可训练、边缘可辨识”，不能写成充分良态。
- 五模态structured bilinear未分解特征：有效秩`561/561=100%`，有效条件数`9.2672e6`，可辨识性明显优于full展开。
- 数据覆盖缺口：train中未接触/接触/强受力比例`4.79%/95.21%/0%`；强受力定义为任一连接点达到轨迹额定力50%。原120条数据不能单独支撑强受力优势，必须由原计划E9和独立confirm验证。
- 协议原SHA256=`45CA993E229611A05AEE97125D53F587D1A95BB6777A94DBCC9F0610079FE443`；细化后SHA256=`285AA7DE1404BF32C0785F6D539B6C9FF10C45969EFC5711307DD6F23BCB98F3`。
- 只读审计脚本SHA256=`220414143E5CE3A0C6DDA4EC7BA5FF80895AA1D10CA2304E01265254F0C47079`；结果写入`revision_2026/koopman/compare/t1/audit.json`和`spectra.npz`。本条结束时尚未训练K2/K3/K4/K5/K6、未生成E9或confirm、未启动闭环。

## W0045 — Koopman比较T0冻结

- 时间：2026-08-22 01:03:40
- 协议hash=285AA7DE1404BF32C0785F6D539B6C9FF10C45969EFC5711307DD6F23BCB98F3，main manifest hash=B3DED2AC3D2F5B0FEE8314DA425632A2E24906243FCB84F3B2379806AF3455CE。
- K0/K1模型hash=B2202FB3579BCE8C00EBAC2A57EE358DF00A04CE06E78CC77B47B9D7E2C11693/A3EA666624E3A01BCE2B173881990906BE1B1A2EEF10465FC82AC92C813757E3；120条development数据角色保持70/15/15/20。
- labels.json只由原70条train计算，hash=3BF81896FF516B9064A7549288365F8FE1DFCE6DB9AB066A13F31A9A888A4FCB。

## W0046 — Koopman比较T1可辨识性与E9

- 时间：2026-08-22 01:03:56
- E9 24条按14/3/3/4生成完成，全部通过有限性、共同ICR及15 kN极限门。
- 原数据K2有效秩=827/837、条件数=9.490499e+07。
- 加入E9-train诊断后有效秩=827/837、条件数=9.550448e+07。
- 原train强受力占比为0；这限制强载荷外推，不影响普通接触区的算子比较。

## W0047 — Koopman比较T2固定lift算子

- 时间：2026-08-22 01:15:53
- K2 validation选择ridge=1e-03；K3选择ridge=1e-06, rank=2；参数匹配K3固定rank=2。
- K0/K1从冻结artifact只读复算；K2/K3及三项冻结消融均完成，模型和窗口级CSV已留存。
- K0–K3的10/25/50/100%嵌套分层学习曲线完成，每档5个subset seed。
- development macro J_pred={"K0": 0.170765, "K1": 0.160109, "K2": 0.184893, "K3": 0.422147, "K3-r2": 0.422147}。

## W0048 — Koopman比较T3机制分离

- 时间：2026-08-22 01:31:20
- K4完成5 seed，代表seed=82044（validation最接近五seed中位数），不是最好seed。
- K5线性源=K1、双线性源=K2，各5 seed并按相同规则固定代表模型。
- K6=not_applicable；冻结样本门统计={"straight": {"windows": 864, "trajectories": 14}, "curve": {"windows": 1540, "trajectories": 14}, "transition": {"windows": 1021, "trajectories": 28}, "sample_gate_pass": false}。
- K4的10/25/50/100%五组嵌套学习曲线已与K0–K3合并。

## W0049 — Koopman比较T4一次性确认

- 时间：2026-08-22 01:48:44
- confirm按冻结seed生成140条（100 internal + 40 external），manifest hash=6ACA00340C4D5A113141D1413820F033228CD625F3D8BE41BA732E3351B299A2。
- 全部模型只读评估；未用confirm重选ridge/rank/seed/epoch/阈值。
- Holm校正后且同时通过8%/CI/5%/非发散/实时/方向复现门的候选=[]。

## W0050 — Koopman比较T5门禁结论

- 时间：2026-08-22 01:49:00
- G4无离线候选，按预注册规则T5=not_applicable_no_offline_candidate；未降低门槛生成闭环图。

## W0051 — Koopman比较T6最终图谱

- 时间：2026-08-22 01:49:34
- 8张要求图及对应CSV/JSON完成；final_report hash=A11042D842349EE911FE750F7B98641B157CA93394912902C94C7B892B8C61B2。
- confirm macro排序=['K0', 'K1', 'K5-linear', 'K4', 'K2', 'K3', 'K3-r2', 'K5-bilinear']；联合门优势组合={}。
- 明确保留三项边界：E9无confirm、强载荷覆盖为0、18D输出不能独立验证作用—反作用两侧。

## W0052 — Koopman比较交付固化与展示审计

- 时间：2026-08-22。
- 计算修复留痕：T2首次实现中，旧artifact的`lifted`标签被错误送入神经lift分支；已改为固定lift。K3最优rank恰为2、与参数匹配对照重合时，原实现复用了同一对象并在后续拟合中覆盖；已改为深拷贝独立对象。两项均属实现错误修复，没有改变预注册模型、数据、seed、指标或阈值；修复后T2及其下游阶段从头重算。
- 最终计算脚本SHA256：`koopman/compare_pipeline.py`=`9170A3085B0C717BAA0E388B2BBA329FE79F838C8ADB235C1C56292FBDD30B79`；`koopman/generate_compare.py`=`87BA89625A81B839DC4F478D4A822D99D963D34345B26C715C9FA49D86385BB2`。W0045的T0冻结早于这两项修复；W0049一次性confirm及当前交付均使用上述最终脚本。协议hash保持`285AA7DE1404BF32C0785F6D539B6C9FF10C45969EFC5711307DD6F23BCB98F3`。
- 展示修复留痕：K5-bilinear数值失败产生的极端值会压扁热图、时域图、Pareto图和OOD图。确认集计算结束后，仅从冻结CSV重绘：热图显示截断为±100%并把越界格标为`NUM FAIL`，时域/学习曲线/Pareto采用对数轴，OOD图不让K5-bilinear失败柱支配比例尺并明确标注数值失败。没有修改CSV、统计量、Holm结果、模型排序或门禁结论。
- 展示脚本SHA256：`koopman/replot_results.py`=`B5ECBE82A232F5809D1BAB9C2060B7D79A4BA101C16D66EB015677C404604306`；展示清单=`koopman/compare/presentation_manifest.json`。
- 最终报告已根据冻结结果补全各场景、各方法优劣与物理证据边界，SHA256=`E8F3376C3040CBEAE541F7143213CCA375924424FB7D173A464108B8DB0EFB92`。它替代W0051记录的早期简版报告hash，但不改W0051的计算结果。
- 最终结论：没有复杂候选通过全部离线门；K0为当前确认域总体验证默认，K1在E5及货物载荷方向判别上更好；K2仅在E0和development E9局部占优但跨场景不稳；K3/K4整体误差偏高；K5-linear只在development E9体现价值；K5-bilinear发生数值失败；K6因样本门不足不适用；T5按预注册规则不启动闭环。


## W0053 — 普适性实验T0冻结与历史复现门

- 协议hash=DF6EE9810137687B9C3814040FFF827DB1DC2DFAE1ED2F2045E6F2618F69BCF7；执行脚本hash=0E153987547B683930882FC86C3B3904D40D52517FA25F7B310422BC3D77DD97。
- B0–B5B artifact匹配={'K2': True, 'K3': True, 'K3-r2': True, 'K4': True, 'K5-linear': True, 'K5-bilinear': True}；历史140条confirm文件完整=True。
- 冻结结果只读macro复核={'K0': 0.12513541290453, 'K1': 0.13283731952714745, 'K2': 0.4023273784857165, 'K3': 0.44346566324356557, 'K3-r2': 0.44346566324356557, 'K4': 0.40143743177289654, 'K5-linear': 0.16730901051004596, 'K5-bilinear': 3928981162.612287}；G0=FAIL。
- 本阶段未生成D1/D2、未训练F/H/T/C/A、未启动闭环。


## W0053R — 普适性实验T0冻结与历史复现门

- 协议hash=DF6EE9810137687B9C3814040FFF827DB1DC2DFAE1ED2F2045E6F2618F69BCF7；执行脚本hash=06DF6742D6973853882D45CEC4A1127DC87937640B53FD8688538249D5E76441。
- B0–B5B artifact匹配={'K2': True, 'K3': True, 'K3-r2': True, 'K4': True, 'K5-linear': True, 'K5-bilinear': True}；历史140条confirm文件完整=True。
- 冻结结果只读macro复核={'K0': 0.12513541290453, 'K1': 0.13283731952714745, 'K2': 0.4023273784857165, 'K3': 0.44346566324356557, 'K3-r2': 0.44346566324356557, 'K4': 0.40143743177289654, 'K5-linear': 0.16730901051004596, 'K5-bilinear': 3928981162.612287}；G0=PASS。
- 首次G0因K5-bilinear十位数量级均值的手工常数少保留约4.77e-7而失败；已用冻结JSON经Python计算的精确float修复并保留初始失败文件，未改模型/数据/协议。
- 本阶段未生成D1/D2、未训练F/H/T/C/A、未启动闭环。


## W0054 — 普适性实验T1强受力覆盖门

- 预注册96配置全部运行；合法配置=0/96，失败配置=96。
- 合法峰值连接力=0.00 N（额定力0.00%）；L3配置=0，L3互不重叠20步窗=0。
- G1=FAIL（failed_no_L3_in_coarse_scan）；按冻结协议T2–T9均不适用，未训练F/H/T/C/A、未生成D1/D2、未启动闭环。
- 扫描CSV hash=A094C9C70E5E09A457636C2209877C2783D408CE6780E64AA2E3370EB229AC0F；图片hash=D52613EF94ABD6AF063E7752251E916B1F43ED183874191F72F7ED68E3432324；solutions hash=FFCEF976E39435E9DDAC2FE8AB852DCFD826EEE05A66DD4D68224009802FC9CA。


## W0054 — 普适性实验T1强受力可行性扫描

- 96配置和五seed重复通过；允许继续生成D1。峰值=12994.05 N。


## W0055 — 普适性实验D1数据与完整G1覆盖门

- D1完成=368/368，失败=[]；覆盖={'train': {'L0': 8016, 'L1': 3808, 'L2': 1398, 'L3': 927, 'L4-high': 11, 'R0': 88, 'R1': 2733, 'R2': 11046, 'R3': 2612, 'R4': 1019, 'R5': 5141, 'trajectories': 240}, 'validation': {'L0': 2122, 'L1': 1036, 'L2': 367, 'L3': 249, 'L4-high': 2, 'R0': 24, 'R1': 745, 'R2': 2921, 'R3': 721, 'R4': 242, 'R5': 1397, 'trajectories': 64}, 'development-test': {'L0': 2149, 'L1': 1023, 'L2': 359, 'L3': 235, 'L4-high': 10, 'R0': 17, 'R1': 782, 'R2': 2903, 'R3': 739, 'R4': 296, 'R5': 1361, 'trajectories': 64}}。
- G1完整覆盖门=FAIL；按协议停止T2–T9。
- D1 manifest hash=F9B37C3E0746E15E3EB45EBB0BE4B9A7C3193EF552C8B25187FCE00A2DFDAFDE；solutions hash=20A5E2A6E648551F352C011A26DDC878F71FF5BFF633222B9FF9B7EB11E47518。


## W0056 — 普适性实验G1停止报告固化

- 纠正早期solutions沿用“扫描无L3”模板的错误；真实结论为扫描通过但D1 train L3=927/1000。
- 方向平衡只读审计={'train': {'Q_FR': True, 'Q_LR': True, 'steering': True}, 'validation': {'Q_FR': True, 'Q_LR': True, 'steering': True}, 'development-test': {'Q_FR': True, 'Q_LR': True, 'steering': True}}；D1最大力=9958.97 N，最大ICR残差=3.280e-13 m/s，ultimate步数=0。
- 最终报告hash=41C9F12D34B48ED9042B6B30762624AAF42333F33CCF7BE2D2D66C5445B3A3CD；solutions hash=09DD9AF01B0E972029FE80FB278DC19F9ED610A6833B655F624DE8B9E1A090A7；停止manifest hash=852907BA2F0066C8FC0DBCC56994D9EA3950C4ED01285EF2C2C7F5243F1FA589。
- 未改协议、seed、D1文件或门槛；未训练F/H/RLS/T/C/A，未生成D2，未启动闭环。


## W0057 — 普适性v2 D1覆盖修正

- 保留v1失败并新增冻结强受力轨迹36条；完成=36/36，失败=[]。
- v2覆盖={'train': {'L0': 8646, 'L1': 4033, 'L2': 1631, 'L3': 1275, 'L4-high': 83, 'R0': 88, 'R1': 3032, 'R2': 12233, 'R3': 2891, 'R4': 1274, 'R5': 6017, 'trajectories': 264}, 'validation': {'L0': 2286, 'L1': 1088, 'L2': 396, 'L3': 378, 'L4-high': 5, 'R0': 24, 'R1': 793, 'R2': 3244, 'R3': 765, 'R4': 312, 'R5': 1616, 'trajectories': 70}, 'development-test': {'L0': 2275, 'L1': 1107, 'L2': 476, 'L3': 285, 'L4-high': 10, 'R0': 17, 'R1': 844, 'R2': 3215, 'R3': 797, 'R4': 338, 'R5': 1579, 'trajectories': 70}}；G1=PASS；train L3 20%余量目标=PASS。
- v2协议hash=AF47ED91A5E918159AFFE072F98D5A135ECB7439876E11CF01654A1C5A9EBB94；combined manifest hash=83FC7A6E2AEA7EA4FDD35EE24E1922402D6C7D0B97D6843329B3624112D00797。


## W0058 — 普适性v2 T2骨干审计

- G2合格骨干=[]；排除=['K0', 'K1', 'K2', 'K3', 'K3-r2', 'K4', 'K5-linear', 'K5-bilinear']。
- 所有骨干均在D1-v2 train归一化下只读复算；条件数/秩/发散仅作分支淘汰，不再全局停止。
- backbone audit hash=EDC9143514D8778F8C346DB02194E170FDF73C70BF072098D8CCF3FDA4CD1CFD；结果hash=555756C16E4E5C03F5B3FB92E0EE13B1089852AB836929DECA3835304FC380C3。


## W0059 — G2入口卡口逻辑勘误

- 保留首次G2全排除结果；识别到以长时域性能作为H入口会造成逻辑自锁。
- 按有限值/条件数/有效秩重分类，F/H入口=['K0', 'K1', 'K4', 'K5-linear']；其余骨干只保留诊断。
- 勘误hash=A448DF35D6B0F6EC3ED54356120D0F0596A321FDC3F13CD69709ED557BCBE865；未降低模块后的状态保护、发散或部署门。


## W0060 — v2 T3因果物理受力头

- 在G2重分类骨干['K0', 'K1', 'K4', 'K5-linear']上完成F0/F1/F2；通过8%相对门的家族数=0/4。
- F2只替换8维四点力，Q与因果力变化率统一重构；状态逐元素未改。
- 结果hash=6CF10DC383253F0954708481E314C3B969DEF7D2FC403DBB3276713A10D4900A；模型目录=D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026\koopman\universal_v2\t3\models。


## W0061 — F词典序回退冻结

- 发现初版F结果只在F2网格内选择，遗漏S规则要求的原骨干F0回退点；未重训、未改数据或候选。
- 按validation选择并用development门决定BFH头：{'K0': 'F0', 'K1': 'F0', 'K4': 'F0', 'K5-linear': 'F0'}。
- selection hash=0CF3DCC20EDE98C69EBA23EA78DD29A1450413E51D37EBA714F1DE803539DE8A。


## W0062 — v2 T4直接多时域H

- H-LS/H-RLS在四个入口骨干完成；8%+状态保护+发散不增门通过=0/4。
- RLS使用与LS相同特征、标准化、rank、ridge和有序样本；lambda=1与batch解作为必须保留回退。
- 结果hash=6EDAC02A31C7DBC14E10F11B4202E43A3F73682AB51366ED2338CFEBF08D29B7；逐时域CSV hash=80FDF6BCD9D65FD266F00C63CE45A936641BCC796D8636D36ADE7BAD6B6484AE。


## W0063 — 参数任务数据生成

- 冻结38个maximin-LHS参数任务；生成train/validation/development前30任务×3场景=90/90，失败=0。
- 参数表hash=229AF88EC5583FD843BD8E25B262B3B6D2F0DB5C267CE533045AFD294661E822；manifest hash=8070FE8A0EBF7BA4CA732254A9446D204598B5D7FC032978B7DD387C29827F1A。
- 任务失败不替换参数组合或seed；future-confirm 8任务留到D2冻结后生成。


## W0064 — v2 T5时间一致性/重新升维机制门

- 逐骨干潜空间漂移诊断完成；C实际运行=['K1', 'K4', 'K5-linear']。
- T状态=not_applicable_no_nonzero_legal_H；没有合法非零H时不为凑实验强训T。
- 机制hash=E9D6C95C9819FE6D27D58AC1283F29CE54EEB4B9841B4F41887A8F970C34D198；C结果hash=E87CA0FD49067EE5D8A4EAEDCD6ED0C1D00099FA838D95329524684E3B267A6F。


## W0065 — v2 T5参数共享低秩适应

- A0/A1(1/2/5s)/A2-online在4骨干、5个development参数任务上完成；通过=['K5-linear']。
- 共享基底只由20个train参数任务的一步残差学习；validation选rank/prior，development不调参。
- 结果hash=AE50E3E3470DFA484567BFA93028515E0B7DCC51B3D03F9806C44809CCB3785C；CSV hash=7FFE2FBA623DC81BB97E8FDD98D553E8606FC7EA7B9134B532E568DB08F75EEA。


## W0066 — 参数范围实现错误归档

- 首轮参数任务误用了历史external极值范围；90条轨迹和A结果全部移入invalid_parameter_range_20260822，不作为证据。
- 修复为预注册范围：质量0.85–1.15、刚度0.75–1.25、阻尼0.70–1.30、间隙0.70–1.40、附着0.80–1.10；maximin候选恢复100。
- 参数任务、90条轨迹和A必须整批重算；D1/F/H/T/C未依赖该参数集，无需重算。


## W0063 — 参数任务数据生成

- 冻结38个maximin-LHS参数任务；生成train/validation/development前30任务×3场景=90/90，失败=0。
- 参数表hash=3F76F05AD472198249D0223DE9244A8CFBB4140414A3331162C0EDAC9C5BDF1A；manifest hash=5D8FA8DE1902AC2697948AE3F801DE8B87C0ED6F7D4417DB8164671F84E004C9。
- 任务失败不替换参数组合或seed；future-confirm 8任务留到D2冻结后生成。


## W0065 — v2 T5参数共享低秩适应

- A0/A1(1/2/5s)/A2-online在4骨干、5个development参数任务上完成；通过=['K5-linear']。
- 共享基底只由20个train参数任务的一步残差学习；validation选rank/prior，development不调参。
- 结果hash=6D98DB83633AFDC5A5C23E14971CD3A00CC83B2FC1BB804FCA8F549FBBDA588E；CSV hash=1540135F2452C6AC2E6322EB74EEF7EA9277E0665948095286CB1B60C879E5C4。


## W0067 — v2 D2一次性确认集生成

- 冻结后生成internal=160/160、external=24/24、network=40/40；失败=[]。
- network文件复用对应internal plant真值，只叠加mask/AoI/trace；确认文件生成后设只读。
- freeze hash=F198C275370B4E169D461FE6FF5A98C3BA2AF1370AECE9A769BE8C329DEA53DD；manifest hash=E7D3EADF70C36126B76A1C15B3E6AB29039FA40E24AB4820BCE4341528EA23A3。


## W0068 — v2 D2一次性确认

- 一次性评估全部冻结有限候选；internal通过=[]；参数适应复现=['K5-linear']。
- F/H跨家族门未在development通过，因此无论confirm局部结果如何均不授予普适性；绝对部署候选为空。
- 结果hash=FEC238B83167809F8325867151F9DF3C022E646552E4D1ACF3C07519043C14EB；门禁hash=DDA191FD3C563A50368DE95834ED4A847D154031B2F19AC6E31E0674BFD49AEC。


## W0069 — v2诊断闭环

- 绝对部署候选为空，正式闭环=0；统一有限控制集20步适配器完成诊断=230/230，失败=0。
- K0/K1覆盖100m clean、单移线、回头弯以及IID/burst/delay/DoS有无状态传播保护；K5+A只做外部参数回头弯。
- 结果hash=72AF639FF7486444A2ADE9ED461A7D964F2EFA5C01F30C2DD6BC1FF76C91C4AC；全部标记diagnostic_only_offline_gate_failed。


## W0070 — 参数闭环配对补充

- 识别到首轮K5参数闭环持续更新，按事实重标A2-online；补跑K0/K1/K5-A0/K5-A1-2s同seed=40/40，失败=0。
- A1只使用前2s残差后冻结，A2保留持续1步残差更新；不得混写。
- 结果hash=9E613E4A8CE26AA0F91A9B91B944F6807B45022E672D7FFBF242E9B1311EF2EA。


## W0071 — v2最终报告与图表

- 生成12张结果图及对应CSV/JSON；缺失=[]。
- 最终结论：跨骨干普适性不成立；K5 few-shot参数适应为唯一复现的局部信号；正式部署候选=0。
- final report hash=3E7CD3B2AE5D81945CDB44C4A6253311FF789E60E01021495326DED149244790；solutions hash=85A745BD5A3E39B751FCBA548DE3962726E7F7A0391FAE5030882FFD67789BDA。


## W0072 — D2 external A配对统计复核

- 对冻结D2 external按24条轨迹做10000次配对bootstrap并对4骨干Holm校正；通过=['K5-linear']。
- 统计hash=301687B64445E572B53C995C36EBCBFD062D2911949D2747B3F27AA916A8499B；保留初始均值门文件universality_gates_initial.json。
- 未修改模型、候选、D2数据或超参数；只补齐预注册统计判定。


## W0073 — 最终报告external统计补审

- 补齐K5 external A的24轨迹配对bootstrap与4骨干Holm校正；K5 A1-2s均值改善10.01%，95% CI 9.18%–10.88%，统计门通过。
- K0/K1/K4统计门不通过；正式部署候选仍为0，跨骨干普适性结论不变。
- 更新后final report hash=C8FD9D562632DDE8EA439C21933A3E3707ABAD62481CDDC8C993E1519AB93E54；统计hash=301687B64445E572B53C995C36EBCBFD062D2911949D2747B3F27AA916A8499B。


## W0074 — G6恢复确认

- 原D2降级为协议路径变更后的审计集；全新D3完成160 internal+24 external+40 network并一次性评估。
- D3 internal通过=[]；external适应通过=['K5-linear']；正式部署候选仍为0。
- 结果hash=51C1A8745B63A629C39A38E17F461951DF1EBCDDC66FBC3A3166A21B5435F2BC；最终门hash=351B99AC57D68FCE215CA4D62295643831EB6E4058BBAE4A37BDD21C13A19102。


## W0071 — v2最终报告与图表

- 生成12张结果图及对应CSV/JSON；缺失=[]；最终确认版本=D3-recovery。
- 最终结论：跨骨干普适性不成立；K5 few-shot参数适应为唯一复现的局部信号；正式部署候选=0。
- final report hash=483AE5659B765ACF10895D43CC5A7CE959699771B54F85CF9AFAF8A096FC63CE；solutions hash=37B9D1087E35966D1F796EA7F27EF16639B82C5DDA784A992374C130EC36BE3E。


## W0075 — D3最终报告hash复核

- D3 K5 external A的24轨迹配对bootstrap与4骨干Holm校正通过；K5 A1-2s均值改善10.19%，95% CI 9.39%–11.03%。
- K0/K1/K4统计门不通过；正式部署候选仍为0，跨骨干普适性结论不变。
- 更新后final report hash=8660BE7235A7BF9DCB97B440C67034098EB8DB743ADBA73CF1E0AED05B26F9B9；统计hash=07B33719009574CCDE9785B360EA661C7DF6B23A024C4CFEF3324E33258A9F0E。
