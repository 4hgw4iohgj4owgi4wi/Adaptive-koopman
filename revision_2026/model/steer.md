# ICR转向分配

## 1. 采用依据

多轴全轮转向文献要求所有滚动方向的法线交于同一瞬时转动中心（ICR），并满足各轮横向无滑移约束。对刚体平面速度 `xi=[Vx,Vy,omega]`，位于 `r_i=[x_i,y_i]` 的点具有：

```text
v_i=[Vx-omega*y_i, Vy+omega*x_i]
```

车辆/轮的目标方向必须与 `v_i` 平行；其法向速度应为0。

虚拟前后转角先用于确定阵列ICR，而不是直接复制给四辆车：

```text
y_ICR=L_array/(tan(delta_f)-tan(delta_r))
x_ICR=L_array/2-y_ICR*tan(delta_f)
```

然后对四个车辆参考点分别计算：

```text
v_i=omega*[-(y_i-y_ICR), x_i-x_ICR]
chi_i=atan2(v_iy,v_ix)
speed_i=||v_i||
delta_ff_i=atan(L_vehicle*omega/speed_i)
```

`chi_i` 是车辆车体相对货物的目标方向；`delta_ff_i` 才是该车辆自身自行车模型的转向角。二者不得混用。

## 2. 动态分配

由于阶跃时车体方向不能瞬间跳变，单车转角采用：

```text
delta_i=delta_ff_i+k_heading*wrap(psi_payload+chi_i-psi_i)
```

并限于 `±15°`。四车目标速度按各自ICR半径分配，速度修正减去四车均值，保证转向阶段的阵列平均加速度指令仍为0：

```text
a_corr_i=k_speed*(speed_des_i-vx_i)
a_corr_i←a_corr_i-mean(a_corr)
```

## 3. 先验验收

- 四个目标速度的ICR法向残差接近0；
- 左右阶跃时ICR和目标方向镜像；
- 稳态同一转弯中四车 `delta_ff` 产生同号横摆率；
- 直行时ICR退化为无穷远，四车目标方向和转角均为0；
- 通过纯运动学测试后才能重跑100m动力学。

## 4. 来源边界

采用的是论文中的共同ICR和无侧滑几何关系，代码按本项目四车锚点和自行车状态合同重新实现，不逐字复制论文代码。文献公式针对刚体多轮/多轴系统；本文增加的车体方向反馈和四车速度零和修正属于针对四个独立车体的工程扩展，必须单独消融验证。

主要来源：

- Zhao Bin, Gao Feng, Lei Tian, *Normalized Coupling Method for Speed Synchronization of Multi-Axis Driving Vehicles*：共同ICR、轮向速度Jacobian和横向无滑移约束。`https://doi.org/10.5772/51153`
- Pingxia Zhang, Li Gao, Yongqiang Zhu, *Study on control schemes of flexible steering system of a multi-axle all-wheel-steering robot*：多轴左右轮/前后轴转角与ICR的显式关系。`https://doi.org/10.1177/1687814016651556`
- Hiroaki Yamaguchi et al., *Control of two manipulation points of a cooperative transportation system with two car-like vehicles following parametric curve paths*：协同搬运中车式机器人与货物连接点的运动学约束。`https://doi.org/10.1016/j.robot.2014.07.007`
