"""模块注册表：二十个模块的状态序列与动作规则的唯一出处。

规则约定（所有模块一致，不再各写各的）：

1. ``status_order`` 是该模块唯一的状态序列；``actions`` 里第 N 个动作负责把记录
   从第 N 档推进到第 N+1 档。动作只能沿序列逐级往下走，回退、跳级、停在原档
   一律由统一引擎拦下并说明原因。
2. 各模块**既有动作名保持不变**。旧代码里部分动作指向回退档，或两个动作抢同一档
   （注释中标了“归位”），统一后按既定状态序列重新归位；动作入口、列表、明细
   读到的可执行动作都由这一处推导，不再各抄一份。
3. ``required_fields`` 沿用登记时的必填字段。

需要新增模块时只在这里登记一条，服务层、接口与前端读到的可执行动作会自动对齐。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleSpec:
    """单个模块的统一规则描述。"""

    name: str
    title: str
    label: str               # 记录称谓，用于错误提示
    status_order: tuple[str, ...]
    actions: tuple[str, ...]
    required_fields: tuple[str, ...]
    keyword_field: str       # 列表检索所依据的编号字段
    negative_action: str | None = None   # 标记为异常的动作（如备件停用）

    def __post_init__(self) -> None:
        if len(self.actions) != len(self.status_order) - 1:
            raise ValueError(
                f"模块 {self.name}：动作数必须比状态档数少 1（逐级推进），"
                f"现有 {len(self.actions)} 个动作、{len(self.status_order)} 档状态"
            )
        if len(set(self.actions)) != len(self.actions):
            raise ValueError(f"模块 {self.name} 的动作名存在重复：{self.actions}")

    @property
    def action_rules(self) -> dict[str, str]:
        """动作名 -> 目标状态：第 N 个动作推进到第 N+1 档，由序列结构唯一确定。"""
        return {
            action: self.status_order[index + 1]
            for index, action in enumerate(self.actions)
        }

    def step_of(self, status: str | None) -> int:
        """返回当前状态所处的档位序号；不在序列内时按 -1 处理。"""
        try:
            return self.status_order.index(status or "")
        except ValueError:
            return -1


_MODULES: tuple[ModuleSpec, ...] = (
    ModuleSpec(
        name="register", title="使用登记", label="设备",
        status_order=("待登记", "已登记", "停用中", "已注销"),
        actions=("办理登记", "申请停用", "申请注销"),
        required_fields=("设备编号", "设备名称", "设备种类"),
        keyword_field="设备编号",
    ),
    ModuleSpec(
        name="boiler", title="锅炉管理", label="锅炉",
        status_order=("正常运行", "低负荷", "检修中", "已停炉"),
        # 归位：旧映射里「恢复运行」指回第一档；统一后作为末档动作推进到已停炉。
        actions=("降负荷运行", "停炉检修", "恢复运行"),
        required_fields=("锅炉编号", "锅炉型号", "额定蒸发量"),
        keyword_field="锅炉编号",
    ),
    ModuleSpec(
        name="pressurevessel", title="压力容器", label="压力容器",
        status_order=("正常", "超压运行", "检验中", "已停用"),
        actions=("降压运行", "安排检验", "办理停用"),
        required_fields=("容器编号", "容器类别", "设计压力"),
        keyword_field="容器编号",
    ),
    ModuleSpec(
        name="pipeline", title="压力管道", label="压力管道",
        status_order=("正常", "壁厚减薄", "待检验", "已报废"),
        actions=("记录减薄", "安排检验", "申请报废"),
        required_fields=("管道编号", "管道级别", "设计压力"),
        keyword_field="管道编号",
    ),
    ModuleSpec(
        name="elevator", title="电梯管理", label="电梯",
        status_order=("正常运行", "维保中", "困人", "检修中"),
        # 归位：旧映射里「困人救援」从维保中直接跳到检修中、「故障检修」指回第一档；
        # 统一后困人救援推进到困人档、故障检修推进到检修中档。
        actions=("安排维保", "困人救援", "故障检修"),
        required_fields=("电梯编号", "电梯类型", "额定载重"),
        keyword_field="电梯编号",
    ),
    ModuleSpec(
        name="crane", title="起重机械", label="起重机",
        status_order=("正常", "超载运行", "检验中", "已停用"),
        actions=("降载运行", "安排检验", "办理停用"),
        required_fields=("起重机编号", "起重机类型", "额定起重量"),
        keyword_field="起重机编号",
    ),
    ModuleSpec(
        name="forklift", title="场车管理", label="场内车辆",
        status_order=("正常", "维修中", "待年检", "已报废"),
        actions=("安排维修", "安排年检", "申请报废"),
        required_fields=("车辆编号", "车辆类型", "动力类型"),
        keyword_field="车辆编号",
    ),
    ModuleSpec(
        name="inspection", title="定期检验", label="检验任务",
        status_order=("待检验", "检验中", "合格", "不合格"),
        actions=("安排检验", "录入结论", "下达整改"),
        required_fields=("检验编号", "被检设备", "检验类别"),
        keyword_field="检验编号",
    ),
    ModuleSpec(
        name="maintenance", title="维保记录", label="维保记录",
        status_order=("待维保", "维保中", "已完成", "需返工"),
        actions=("安排维保", "开始维保", "返工登记"),
        required_fields=("维保编号", "维保设备", "维保单位"),
        keyword_field="维保编号",
    ),
    ModuleSpec(
        name="hazard", title="隐患排查", label="隐患",
        status_order=("待整改", "整改中", "待验收", "已消除"),
        actions=("安排整改", "开始整改", "验收消除"),
        required_fields=("隐患编号", "所在设备", "隐患类别"),
        keyword_field="隐患编号",
    ),
    ModuleSpec(
        name="accident", title="事故管理", label="事故记录",
        status_order=("待上报", "已上报", "调查中", "已结案"),
        actions=("上报事故", "开展调查", "结案归档"),
        required_fields=("事故编号", "事故设备", "事故类型"),
        keyword_field="事故编号",
    ),
    ModuleSpec(
        name="operator", title="作业人员", label="作业人员",
        status_order=("持证有效", "即将到期", "已过期", "已注销"),
        # 归位：旧映射里「安排复审」指回第一档；统一后作为第一档动作推进到即将到期。
        actions=("安排复审", "登记过期", "注销证书"),
        required_fields=("人员编号", "姓名", "证书类别"),
        keyword_field="人员编号",
    ),
    ModuleSpec(
        name="training", title="培训考核", label="培训记录",
        status_order=("待培训", "培训中", "已考核", "已归档"),
        actions=("组织培训", "组织考核", "归档"),
        required_fields=("培训编号", "培训内容", "培训对象"),
        keyword_field="培训编号",
    ),
    ModuleSpec(
        name="safetyvalve", title="安全阀校验", label="安全阀",
        status_order=("校验合格", "即将到期", "待校验", "已报废"),
        # 归位：旧映射里「安排校验」直指待校验、「登记合格」指回首档；
        # 统一后安排校验推进到即将到期、登记合格推进到待校验。
        actions=("安排校验", "登记合格", "申请报废"),
        required_fields=("安全阀编号", "所属设备", "公称通径"),
        keyword_field="安全阀编号",
    ),
    ModuleSpec(
        name="gauge", title="压力表检定", label="压力表",
        status_order=("检定合格", "即将到期", "待检定", "已停用"),
        # 归位：旧映射里「安排检定」直指待检定、「登记合格」指回首档；
        # 统一后安排检定推进到即将到期、登记合格推进到待检定。
        actions=("安排检定", "登记合格", "办理停用"),
        required_fields=("压力表编号", "所属设备", "量程范围"),
        keyword_field="压力表编号",
    ),
    ModuleSpec(
        name="sparepart", title="备件管理", label="备件",
        status_order=("充足", "不足", "待采购", "已停用"),
        # 归位：旧映射里「采购入仓」指回第一档；统一后作为第三档动作推进到待采购。
        actions=("办理领用", "采购入仓", "停用备件"),
        required_fields=("备件编号", "备件名称", "规格型号"),
        keyword_field="备件编号",
        negative_action="停用备件",
    ),
    ModuleSpec(
        name="emergency", title="应急演练", label="演练记录",
        status_order=("待组织", "已组织", "已完成", "已复盘"),
        actions=("组织演练", "完成演练", "复盘总结"),
        required_fields=("演练编号", "演练主题", "演练类型"),
        keyword_field="演练编号",
    ),
    ModuleSpec(
        name="energyeff", title="能效监测", label="能效记录",
        status_order=("达标", "轻微偏差", "显著偏差", "已调整"),
        actions=("记录偏差", "分析原因", "调整优化"),
        required_fields=("记录编号", "设备类型", "耗能量"),
        keyword_field="记录编号",
    ),
    ModuleSpec(
        name="archive", title="档案管理", label="档案",
        status_order=("在库", "借出中", "已归还", "已销毁"),
        # 归位：旧映射里「登记归还」指回第一档；统一后作为第三档动作推进到已归还。
        actions=("办理借阅", "登记归还", "申请销毁"),
        required_fields=("档案编号", "所属设备", "档案类别"),
        keyword_field="档案编号",
    ),
    ModuleSpec(
        name="contract", title="维保合同", label="合同",
        status_order=("待签约", "执行中", "即将到期", "已终止"),
        # 归位：旧映射里「到期续签」与「签订合同」抢同一档执行中；
        # 统一后到期续签推进到即将到期。
        actions=("签订合同", "到期续签", "终止合同"),
        required_fields=("合同编号", "签约单位", "维保范围"),
        keyword_field="合同编号",
    ),
)


class Registry:
    """按模块名索引规则，给服务层与接口层共用。"""

    def __init__(self, specs: tuple[ModuleSpec, ...]) -> None:
        self._specs: dict[str, ModuleSpec] = {spec.name: spec for spec in specs}

    def get(self, module: str) -> ModuleSpec:
        if module not in self._specs:
            raise KeyError(f"模块「{module}」未在统一规则表中登记")
        return self._specs[module]

    def names(self) -> list[str]:
        return sorted(self._specs)

    def all(self) -> tuple[ModuleSpec, ...]:
        return tuple(self._specs.values())

    def owner_of(self, action: str) -> str | None:
        """反查动作归属的模块；不属于任何模块时返回 None（越权/误投判定用）。"""
        for spec in self._specs.values():
            if action in spec.action_rules:
                return spec.name
        return None


registry = Registry(_MODULES)
