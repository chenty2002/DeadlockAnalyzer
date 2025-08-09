class ParamConfig:
    l1_way_bits = 1

    l1_tag_bits = 3
    l1_set_bits = 1
    l1_offset_bits = 1


    l2_way_bits = 1

    l2_tag_bits = 2
    l2_set_bits = 2
    l2_offset_bits = 1


    l3_way_bits = 1

    l3_tag_bits = 2
    l3_set_bits = 2
    l3_offset_bits = 1

    addr_bits = 5
    
    l3_granularity = 1


def get_level_str(level, i):
    if i == 1:
        suffix = '_1'
    else:
        suffix = ''
    if level == 'l1':
        return 'coupledL2AsL1' + suffix
    elif level == 'l2':
        return 'coupledL2' + suffix
    else:
        return ''

def get_l1_addr(tag, set):
    return tag << (ParamConfig.l1_set_bits + ParamConfig.l1_offset_bits) | set << ParamConfig.l1_offset_bits

def get_l2_addr(tag, set):
    return tag << (ParamConfig.l2_set_bits + ParamConfig.l2_offset_bits) | set << ParamConfig.l2_offset_bits

def get_l3_addr(tag, set):
    return tag << (ParamConfig.l3_set_bits + ParamConfig.l3_offset_bits) | set << ParamConfig.l3_offset_bits

def l3_set_block(set1, set2):
    return (set1 & (1 << ParamConfig.l3_granularity -1)) == (set2 & (1 << ParamConfig.l3_granularity -1))

def parse_l1_addr(addr):
    offset = addr & ((1 << ParamConfig.l1_offset_bits) - 1)
    set = (addr >> ParamConfig.l1_offset_bits) & ((1 << ParamConfig.l1_set_bits) - 1)
    tag = addr >> (ParamConfig.l1_offset_bits + ParamConfig.l1_set_bits)
    return (tag, set, offset)

def parse_l2_addr(addr):
    offset = addr & ((1 << ParamConfig.l2_offset_bits) - 1)
    set = (addr >> ParamConfig.l2_offset_bits) & ((1 << ParamConfig.l2_set_bits) - 1)
    tag = addr >> (ParamConfig.l2_offset_bits + ParamConfig.l2_set_bits)
    return (tag, set, offset)

def parse_l3_addr(addr):
    offset = addr & ((1 << ParamConfig.l3_offset_bits) - 1)
    set = (addr >> ParamConfig.l3_offset_bits) & ((1 << ParamConfig.l3_set_bits) - 1)
    tag = addr >> (ParamConfig.l3_offset_bits + ParamConfig.l3_set_bits)
    return (tag, set, offset)