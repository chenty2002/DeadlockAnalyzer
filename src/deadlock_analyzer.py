from pywellen import *
from tilelink_consts import *
from param_configs import *
import param_configs
import tilelink_consts
from waitfor_graph import graph_wrapper

# 加载FST文件（替换为实际路径）
# fst_file = "/home/loyce/XiangShan/CoupledL2-Verification/deadlock_analyzer/fst/CoupledL2_L2AsL1_TileLink_mshrCtl死锁_0621_2L2_L3_替换算法拓展.fst"
# fst_file = "/home/loyce/XiangShan/CoupledL2-Verification/deadlock_analyzer/fst/CoupledL2_L2AsL1_TileLink_mshrCtl死锁_0508_2L2_L3_持续发0地址.fst"
fst_file = "/home/loyce/XiangShan/CoupledL2-Verification/deadlock_analyzer/fst/CoupledL2_L2AsL1_TileLink_mshrCtl死锁_0531_2L1_2L2_L3_替换算法.fst"
waveform = Waveform(path=fst_file, multi_threaded=True)

# 获取波形层次结构
hierarchy = waveform.hierarchy

# fst length

timer = waveform.get_signal_from_path('VerifyTop.verify_timer')
timer_changes = list(timer.all_changes())
ns_per_beat = timer_changes[-1][0] - timer_changes[-2][0]
length_ns = timer_changes[-1][0]
print(f'waveform length: {length_ns}ns, 1 beat = {ns_per_beat}ns')


# CoupledL2

# 找到最早停滞的MSHR（任一CoupledL2）
mshr_status = [[], []]
status_changes = [[], []]
mshr_i = [-1, -1]
for l2 in range(2):
    for i in range(16):
        try:
            cpl2_str = 'coupledL2' if l2 == 0 else 'coupledL2_1'
            mshr_i_status = waveform.get_signal_from_path(f'VerifyTop.{cpl2_str}.slices_0.mshrCtl.mshrs_{i}.io_status_valid')
        except RuntimeError:
            try:
                cpl2_str = 'coupledL2' if l2 == 0 else 'coupledL2_1'
                mshr_i_status = waveform.get_signal_from_path(f'VerifyTop.{cpl2_str}.slices_0.mshrCtl.mshrs_{i}.io__status_valid')
            except RuntimeError:
                break
        mshr_status[l2].append(mshr_i_status)
        status_changes[l2].append(list(mshr_i_status.all_changes())[-1])
        if status_changes[l2][-1][1] == 1:
            if mshr_i[l2] == -1 or status_changes[l2][-1][0] < status_changes[l2][mshr_i[l2]][0]:
                mshr_i[l2] = i

# print(status_changes)
# print(mshr_i)

if mshr_i[0] == -1 and mshr_i[1] == -1:
    print('no requests found')
    exit(1)

if mshr_i[0] != -1:
    l2_i = 0
    if mshr_i[1] != -1 and status_changes[0][mshr_i[0]][0] > status_changes[1][mshr_i[1]][0]:
        l2_i = 1
else:
    l2_i = 1

cpl2_str = 'coupledL2' if l2_i == 0 else 'coupledL2_1'
mshr = mshr_i[l2_i]

mshr_t = status_changes[l2_i][mshr][0]


# 若l2_i发送了acquire_block，且MSHR开始处理的时间为mshr_t，返回该请求在l3中处理时的MSHR编号和开始结束时间
def acquire_block(waveform, l2_i, tag, set, mshr_t):
    addr = get_l2_addr(tag, set)
    l1_str = 'coupledL2AsL1' if l2_i == 0 else 'coupledL2AsL1_1'
    l2_str = 'coupledL2' if l2_i == 0 else 'coupledL2_1'
    
    # l1 send to l2
    req_from_l1_valid_sig = waveform.get_signal_from_path(f'VerifyTop.{l2_str}.auto_in_a_valid')
    req_from_l1_ready_sig = waveform.get_signal_from_path(f'VerifyTop.{l2_str}.auto_in_a_ready')
    req_from_l1_addr_sig = waveform.get_signal_from_path(f'VerifyTop.{l2_str}.auto_in_a_bits_address')
    req_from_l1_opcode_sig = waveform.get_signal_from_path(f'VerifyTop.{l2_str}.auto_in_a_bits_opcode')
    req_from_l1_data_sig = waveform.get_signal_from_path(f'VerifyTop.{l2_str}.auto_in_a_bits_data')
    req_from_l1_changes = list(req_from_l1_valid_sig.all_changes())
    l2_receive_t = 0
    
    l1_addr = 0
    l1_opcode = 0
    l1_data = 0
    for t, v in req_from_l1_changes:
        if t > mshr_t:
            break
        if v == 0:
            continue
        if req_from_l1_ready_sig.value_at_time(t) == 0:
            continue
        if req_from_l1_addr_sig.value_at_time(t) != addr:
            continue
        # if (l1_opcode, 1) == TileLinkConsts.AcquireBlock:
        #     l2_receive_t = t
        l1_addr = req_from_l1_addr_sig.value_at_time(t)
        l1_opcode = req_from_l1_opcode_sig.value_at_time(t)
        l1_data = req_from_l1_data_sig.value_at_time(t)
        l2_receive_t = t
            
    print('Last request from L1 channel A:')
    if (l1_opcode, 1) == TileLinkConsts.AcquireBlock:
        print(f'\tAcquireBlock of {l1_addr} with data {l1_data} at {l2_receive_t}ns\n')
    
    # req in l1
    l1_mshr_i = -1
    l1_mshr_start = -1
    l1_mshr_end = -1
    l1_req_set = -1
    l1_req_tag = -1
    l1_req_source = -1
    l1_req_channel = -1
    l1_req_opcode = -1

    for i in range(16):
        try:
            mshr_i_status = waveform.get_signal_from_path(f'VerifyTop.{l1_str}.slices_0.mshrCtl.mshrs_{i}.io_status_valid')
        except RuntimeError:
            try:
                mshr_i_status = waveform.get_signal_from_path(f'VerifyTop.{l1_str}.slices_0.mshrCtl.mshrs_{i}.io__status_valid')
            except RuntimeError:
                break

        l1_req_set_sig = waveform.get_signal_from_path(f'VerifyTop.{l1_str}.slices_0.mshrCtl.mshrs_{i}.req_set')
        l1_req_tag_sig = waveform.get_signal_from_path(f'VerifyTop.{l1_str}.slices_0.mshrCtl.mshrs_{i}.req_tag')
        l1_req_source_sig = waveform.get_signal_from_path(f'VerifyTop.{l1_str}.slices_0.mshrCtl.mshrs_{i}.req_sourceId')
        l1_req_channel_sig = waveform.get_signal_from_path(f'VerifyTop.{l1_str}.slices_0.mshrCtl.mshrs_{i}.req_channel')
        l1_req_opcode_sig = waveform.get_signal_from_path(f'VerifyTop.{l1_str}.slices_0.mshrCtl.mshrs_{i}.req_opcode')

        l1_sig_changes = list(mshr_i_status.all_changes())

        for t, v in l1_sig_changes:
            if v == 1:
                l1_set_tmp = l1_req_set_sig.value_at_time(t)
                l1_tag_tmp = l1_req_tag_sig.value_at_time(t)
                if get_l1_addr(l1_tag_tmp, l1_set_tmp) != l1_addr:
                    continue
                # if l1_req_channel_sig.value_at_time(t) != 1:
                #     continue
                # if l1_req_opcode_sig.value_at_time(t) != l1_opcode:
                #     continue
                l1_req_set = l1_req_set_sig.value_at_time(t)
                l1_req_tag = l1_req_tag_sig.value_at_time(t)
                l1_req_channel = l1_req_channel_sig.value_at_time(t)
                l1_req_opcode = l1_req_opcode_sig.value_at_time(t)
                l1_req_source = l1_req_source_sig.value_at_time(t)
                
                l1_mshr_i = i
                l1_mshr_start = t
            else:
                if l1_mshr_start != -1:
                    l1_mshr_end = t
                    break
            
        if l1_mshr_i != -1:
            break


    if l1_mshr_i == -1:
        print('\trequest not found in l1')
    elif l1_mshr_end == -1:
        l1_mshr_end = length_ns
    
        print(f'\tNo. of L1 MSHR - l1_mshr_i: {l1_mshr_i}\n'
            f'\tStart Time - l1_mshr_start: {l1_mshr_start}ns\n')
        if l1_mshr_end != length_ns:
            print(f'\tEnd Time - l1_mshr_end: {l1_mshr_end}ns\n')
        
        print(f'\tRequest in l1 MSHR:\n'
            f'\treq_set: {l1_req_set}\n'
            f'\treq_tag: {l1_req_tag}\n'
            f'\treq_source: {l1_req_source}\n'
            f'\treq_channel: {l1_req_channel}\n'
            f'\treq_opcode: {l1_req_opcode}\n'
            f'\treq_addr: {get_l1_addr(l1_req_tag, l1_req_set)}')
        if (l1_req_opcode, l1_req_channel) == TileLinkConsts.AcquireBlock:
            print('\tProcessing AcquireBlock\n')
    
    
    # l2 send to l3
    req_to_l3_valid_sig = waveform.get_signal_from_path(f'VerifyTop.{l2_str}.auto_out_a_valid')
    req_to_l3_ready_sig = waveform.get_signal_from_path(f'VerifyTop.{l2_str}.auto_out_a_ready')
    req_to_l3_addr_sig = waveform.get_signal_from_path(f'VerifyTop.{l2_str}.auto_out_a_bits_address')
    req_to_l3_opcode_sig = waveform.get_signal_from_path(f'VerifyTop.{l2_str}.auto_out_a_bits_opcode')
    req_to_l3_data_sig = waveform.get_signal_from_path(f'VerifyTop.{l2_str}.auto_out_a_bits_data')
    req_to_l3_changes = list(req_to_l3_valid_sig.all_changes())
    l2_send_t = mshr_t
    
    l3_addr = 0
    l3_opcode = 0
    l3_data = 0
    for t, v in req_to_l3_changes:
        if t < mshr_t:
            continue
        if v == 0:
            continue
        if req_to_l3_ready_sig.value_at_time(t) == 0:
            continue
        if req_to_l3_addr_sig.value_at_time(t) != addr:
            continue
        l3_addr = req_to_l3_addr_sig.value_at_time(t)
        l3_opcode = req_to_l3_opcode_sig.value_at_time(t)
        l3_data = req_to_l3_data_sig.value_at_time(t)
        l2_send_t = t
        break
            
    print('Next request to L3 channel A:')
    if (l3_opcode, 1) == TileLinkConsts.AcquireBlock:
        print(f'\tAcquireBlock of {l3_addr} with data {l3_data} at {l2_send_t}ns\n')
   
    l3_mask = waveform.get_signal_from_path(f'VerifyTop.{l2_str}.auto_out_a_bits_mask').value_at_time(l2_send_t)
    l3_param = waveform.get_signal_from_path(f'VerifyTop.{l2_str}.auto_out_a_bits_param').value_at_time(l2_send_t)
    l3_size = waveform.get_signal_from_path(f'VerifyTop.{l2_str}.auto_out_a_bits_size').value_at_time(l2_send_t)
    
    # HuanCun

    l3_mshr_i = -1
    l3_mshr_start = -1
    l3_mshr_end = -1
    l3_req_set = -1
    l3_req_tag = -1
    l3_req_source = -1
    l3_req_channel = -1
    l3_req_opcode = -1
    l3_req_mask = -1
    l3_req_param = -1
    l3_req_size = -1
    
    l3_iam = -1

    for i in range(16):
        try:
            mshr_i_status = waveform.get_signal_from_path(f'VerifyTop.l3.slices_0.mshrAlloc.io_status_{i}_valid')
        except RuntimeError:
            try:
                mshr_i_status = waveform.get_signal_from_path(f'VerifyTop.l3.slices_0.mshrAlloc.io__status_{i}_valid')
            except RuntimeError:
                break

        l3_iam_sig = waveform.get_signal_from_path(f'VerifyTop.l3.slices_0.ms_{i}.iam')
        l3_req_set_sig = waveform.get_signal_from_path(f'VerifyTop.l3.slices_0.ms_{i}.req_set')
        l3_req_tag_sig = waveform.get_signal_from_path(f'VerifyTop.l3.slices_0.ms_{i}.req_tag')
        l3_req_source_sig = waveform.get_signal_from_path(f'VerifyTop.l3.slices_0.ms_{i}.req_source')
        l3_req_channel_sig = waveform.get_signal_from_path(f'VerifyTop.l3.slices_0.ms_{i}.req_channel')
        l3_req_opcode_sig = waveform.get_signal_from_path(f'VerifyTop.l3.slices_0.ms_{i}.req_opcode')
        l3_req_mask_sig = waveform.get_signal_from_path(f'VerifyTop.l3.slices_0.ms_{i}.req_mask')
        l3_req_param_sig = waveform.get_signal_from_path(f'VerifyTop.l3.slices_0.ms_{i}.req_param')
        l3_req_size_sig = waveform.get_signal_from_path(f'VerifyTop.l3.slices_0.ms_{i}.req_size')

        l3_sig_changes = list(mshr_i_status.all_changes())

        for t, v in l3_sig_changes:
            if t < l2_send_t:
                continue
            if v == 1: 
                l3_set_tmp = l3_req_set_sig.value_at_time(t)
                l3_tag_tmp = l3_req_tag_sig.value_at_time(t)
                if get_l3_addr(l3_tag_tmp, l3_set_tmp) != l3_addr:
                    continue
                if l3_iam_sig.value_at_time(t)%2 != l2_i:
                    continue
                if l3_req_channel_sig.value_at_time(t) != 1:
                    continue
                if l3_req_opcode_sig.value_at_time(t) != l3_opcode:
                    continue
                l3_req_set = l3_req_set_sig.value_at_time(t)
                l3_req_tag = l3_req_tag_sig.value_at_time(t)
                l3_req_channel = l3_req_channel_sig.value_at_time(t)
                l3_req_opcode = l3_req_opcode_sig.value_at_time(t)
                l3_req_source = l3_req_source_sig.value_at_time(t)
                l3_req_mask = l3_req_mask_sig.value_at_time(t)
                l3_req_param = l3_req_param_sig.value_at_time(t)
                l3_req_size = l3_req_size_sig.value_at_time(t)
                
                l3_iam = l3_iam_sig.value_at_time(t)
                l3_mshr_i = i
                l3_mshr_start = t
            else:
                if l3_mshr_start != -1:
                    l3_mshr_end = t
                    break
            
        if l3_mshr_i != -1:
            break


    if l3_mshr_i == -1:
        print('\trequest not found in L3')
        return -1, -1, -1
    
    if l3_mshr_end == -1:
        l3_mshr_end = length_ns
    
    print(f'\tNo. of L3 MSHR - l3_mshr_i: {l3_mshr_i}\n'
          f'\tStart Time - l3_mshr_start: {l3_mshr_start}ns\n')
    if l3_mshr_end != length_ns:
        print(f'\tEnd Time - l3_mshr_end: {l3_mshr_end}ns\n')
    
    print(f'\tRequest in L3 MSHR:\n'
          f'\treq_set: {l3_req_set}\n'
          f'\treq_tag: {l3_req_tag}\n'
          f'\treq_source: {l3_req_source}\n'
          f'\treq_channel: {l3_req_channel}\n'
          f'\treq_opcode: {l3_req_opcode}\n'
          f'\treq_addr: {get_l3_addr(l3_req_tag, l3_req_set)}')
    if (l3_req_opcode, l3_req_channel) == TileLinkConsts.AcquireBlock:
        print('\tProcessing AcquireBlock\n')
        
    return l3_mshr_i, l3_mshr_start, l3_mshr_end

# iam  cpl2
# 01    1
# 00    0
# 

# 若上一层于start_time发送地址为addr的Probe请求，从level_li中的mshr找到该请求（在end_time之前），返回定位结果
def find_trans_in_mshr(waveform, level, l_i, addr, start_time, end_time, trans):
    level_str = get_level_str(level, l_i)
    req_from_last_valid = waveform.get_signal_from_path(f'VerifyTop.{level_str}.auto_out_b_valid')
    req_from_last_ready = waveform.get_signal_from_path(f'VerifyTop.{level_str}.auto_out_b_ready')
    req_from_last_changes = list(req_from_last_valid.all_changes())
    this_receive_t = 0
    for t, v in req_from_last_changes:
        if t >= start_time:
            if v == 1 and req_from_last_ready.value_at_time(t) == 1:
                this_receive_t = t
                break
    
    this_mshr_i = -1
    this_mshr_start = -1
    this_addr = -1
    this_opcode = -1
    this_channel = -1
    for i in range(16):
        mshr_str = f'VerifyTop.{level_str}.slices_0.mshrCtl.mshrs_{i}'
        try:
            mshr_i_status = waveform.get_signal_from_path(f'{mshr_str}.io_status_valid')
        except RuntimeError:
            try:
                mshr_i_status = waveform.get_signal_from_path(f'{mshr_str}.io__status_valid')
            except RuntimeError:
                break
        
        this_req_set_sig = waveform.get_signal_from_path(f'{mshr_str}.req_set')
        this_req_tag_sig = waveform.get_signal_from_path(f'{mshr_str}.req_tag')
        this_req_source_sig = waveform.get_signal_from_path(f'{mshr_str}.req_sourceId')
        this_req_channel_sig = waveform.get_signal_from_path(f'{mshr_str}.req_channel')
        this_req_opcode_sig = waveform.get_signal_from_path(f'{mshr_str}.req_opcode')
        this_sig_changes = list(mshr_i_status.all_changes())
        
        for t, v in this_sig_changes:
            if t < this_receive_t:
                continue
            if v == 0:
                continue
            
            this_set_tmp = this_req_set_sig.value_at_time(t)
            this_tag_tmp = this_req_tag_sig.value_at_time(t)
            this_addr_tmp = getattr(param_configs, f'get_{level}_addr')(this_tag_tmp, this_set_tmp)
            if this_addr_tmp != addr:
                continue
            if this_req_opcode_sig.value_at_time(t) != trans[0]:
                continue
            if this_req_channel_sig.value_at_time(t) != trans[1]:
                continue
            
            this_set = this_set_tmp
            this_tag = this_tag_tmp
            this_opcode = this_req_opcode_sig.value_at_time(t)
            this_channel = this_req_channel_sig.value_at_time(t)
            this_addr = addr
            
            this_mshr_i = i
            this_mshr_start = t
            break
        if this_mshr_i != -1:
            break
        
    if this_mshr_i == -1:
        # print(f'Request not found in {level_str}')
        return {}, {}
    print(f'Request found in {level_str} mshr {this_mshr_i}: starting from {this_mshr_start}ns\n')
        
    this_send_trans = get_transactions(waveform, TileLinkConsts.l2_state_s_signals, 
                                       f'VerifyTop.{level_str}.slices_0.mshrCtl.mshrs', this_mshr_i, this_mshr_start, end_time)
    this_wait_trans = get_transactions(waveform, TileLinkConsts.l2_state_w_signals, 
                                       f'VerifyTop.{level_str}.slices_0.mshrCtl.mshrs', this_mshr_i, this_mshr_start, end_time)
    
    print(f'{level}_{l_i} signals:')
    for trans, t in this_send_trans.items():
        print(f's_transaction {trans}: starting from {t[0]}ns to {t[1]}ns')
    for trans, t in this_wait_trans.items():
        print(f'w_transaction {trans}: starting from {t[0]}ns to {t[1]}ns')
        
    return this_send_trans, this_wait_trans


# 找出level_li的mshr在start_time和end_time之间处理的所有请求，返回结果
def get_all_trans_in_mshrs(waveform, level, l_i, start_time, end_time):
    level_str = get_level_str(level, l_i)
    
    req_info = []
    for i in range(16):
        mshr_str = f'VerifyTop.{level_str}.slices_0.mshrCtl.mshrs_{i}'
        try:
            mshr_i_status = waveform.get_signal_from_path(f'{mshr_str}.io_status_valid')
        except RuntimeError:
            try:
                mshr_i_status = waveform.get_signal_from_path(f'{mshr_str}.io__status_valid')
            except RuntimeError:
                break
        
        this_req_set_sig = waveform.get_signal_from_path(f'{mshr_str}.req_set')
        this_req_tag_sig = waveform.get_signal_from_path(f'{mshr_str}.req_tag')
        this_req_source_sig = waveform.get_signal_from_path(f'{mshr_str}.req_sourceId')
        this_req_channel_sig = waveform.get_signal_from_path(f'{mshr_str}.req_channel')
        this_req_opcode_sig = waveform.get_signal_from_path(f'{mshr_str}.req_opcode')
        this_sig_changes = list(mshr_i_status.all_changes())
        
        for t, v in this_sig_changes:
            this_set = this_req_set_sig.value_at_time(t)
            this_tag = this_req_tag_sig.value_at_time(t)
            this_opcode = this_req_opcode_sig.value_at_time(t)
            this_channel = this_req_channel_sig.value_at_time(t)
            this_addr = getattr(param_configs, f'get_{level}_addr')(this_tag, this_set)
            if v == 1:
                req_info.append([i, this_addr, this_opcode, this_channel, t, length_ns])
            else:
                if len(req_info) > 0:
                    req_info[-1][-1] = t
    
    req_info = list(filter(lambda x: x[4] < end_time and x[5] > start_time, req_info))
    req_info.sort(key=lambda x: (x[0], x[4], x[5], x[1]))
    if len(req_info) > 0:
        print(f'All requests in {level_str} mshrs (starting from {start_time}ns to {end_time}ns):')
        for req in req_info:
            print(f'mshr {req[0]}: addr {req[1]}, opcode {req[2]}, channel {req[3]}, start {req[4]}ns, end {req[5]}ns')
    else:
        print(f'No requests in {level_str} mshrs (with ANY addr starting from {start_time}ns to {end_time}ns)')
    return req_info
    
    
# 找出level_li的mainpipe在start_time和end_time之间出现的所有请求（task_s4），返回结果
def get_all_trans_in_mainpipe(waveform, level, l_i, start_time, end_time):
    level_str = get_level_str(level, l_i)
    
    req_info = []
    mainpipe_str = f'VerifyTop.{level_str}.slices_0.mainPipe'
    req_bits_str = f'{mainpipe_str}.task_s4'
    mainpipe_status = waveform.get_signal_from_path(f'{req_bits_str}_valid')
    
    req_set_sig = waveform.get_signal_from_path(f'{req_bits_str}_bits_set')
    req_tag_sig = waveform.get_signal_from_path(f'{req_bits_str}_bits_tag')
    req_source_sig = waveform.get_signal_from_path(f'{req_bits_str}_bits_sourceId')
    req_channel_sig = waveform.get_signal_from_path(f'{req_bits_str}_bits_channel')
    req_opcode_sig = waveform.get_signal_from_path(f'{req_bits_str}_bits_opcode')
    # req_needProbeAckData = waveform.get_signal_from_path(f'{req_bits_str}_bits_needProbeAckData')
    
    block_A = waveform.get_signal_from_path(f'{mainpipe_str}.io_toReqArb_blockA_s1')
    block_B = waveform.get_signal_from_path(f'{mainpipe_str}.io_toReqArb_blockB_s1')
    block_C = waveform.get_signal_from_path(f'{mainpipe_str}.io_toReqArb_blockC_s1')
    block_G = waveform.get_signal_from_path(f'{mainpipe_str}.io_toReqArb_blockG_s1')
    sig_changes = list(mainpipe_status.all_changes())
    
    for t, v in sig_changes:
        set = req_set_sig.value_at_time(t)
        tag = req_tag_sig.value_at_time(t)
        opcode = req_opcode_sig.value_at_time(t)
        channel = req_channel_sig.value_at_time(t)
        addr = getattr(param_configs, f'get_{level}_addr')(tag, set)
        
        block_A_val = block_A.value_at_time(t)
        block_B_val = block_B.value_at_time(t)
        block_C_val = block_C.value_at_time(t)
        block_G_val = block_G.value_at_time(t)
        if v == 1:
            req_info.append([addr, opcode, channel, block_A_val, block_B_val, block_C_val, block_G_val, t, length_ns])
        else:
            if len(req_info) > 0:
                req_info[-1][-1] = t
    
    req_info = list(filter(lambda x: x[-2] < end_time and x[-1] > start_time, req_info))
    req_info.sort(key=lambda x: (x[-2], x[-1], x[0]))
    if len(req_info) > 0:
        print(f'All requests in {level_str} mainPipe task_s4 (starting from {start_time}ns to {end_time}ns):')
        for req in req_info:
            print(f'addr {req[0]}, opcode {req[1]}, channel {req[2]}, block_A {req[3]}, block_B {req[4]}, block_C {req[5]}, block_G {req[6]}, start {req[-2]}ns, end {req[-1]}ns')
    else:
        print(f'No requests in {level_str} mainPipe task_s4 (with ANY addr starting from {start_time}ns to {end_time}ns)')
    return req_info
    

# 若l3向l2_i发送了probe但没收到probeack，地址为addr，发送时间为start_time
def probe_ack(waveform, l2_i, addr, start_time, end_time):
    # 从L2的MSHR定位请求
    l2_send_trans, l2_wait_trans = find_trans_in_mshr(waveform, 'l2', l2_i, addr, start_time, end_time, TileLinkConsts.Probe)
    # L2会向L1发相同的Probe
    if len(l2_send_trans) == 0 or len(l2_wait_trans) == 0:
        print(f'\nNo Probe request (addr={addr}) found in l2_{l2_i}')
        mshr_req_info = get_all_trans_in_mshrs(waveform, 'l2', l2_i, start_time, end_time)
        task_s4_req_info = get_all_trans_in_mainpipe(waveform, 'l2', l2_i, start_time, end_time)
        return
    
    
    # L2 发送了Probe给L1但超过500拍没收到ProbeAck
    if 'state_s_pprobe' in l2_send_trans:
        if 'state_w_pprobeack' in l2_wait_trans:
            if l2_send_trans['state_s_pprobe'][1] + 500*ns_per_beat < l2_wait_trans['state_w_pprobeack'][1] or \
                l2_wait_trans['state_w_pprobeack'][1] == length_ns:
                print(f'L2_{l2_i} sent a Probe request (pprobe) to L1_{l2_i} but did not receive ProbeAck')
    
    l1_send_trans, l1_wait_trans = find_trans_in_mshr(waveform, 'l1', l2_i, addr, start_time, end_time, TileLinkConsts.Probe)
    if len(l1_send_trans) == 0 or len(l1_wait_trans) == 0:
        print(f'\nNo Probe request (addr={addr}) found in l1_{l2_i}')
        mshr_req_info = get_all_trans_in_mshrs(waveform, 'l1', l2_i, start_time, end_time)
        task_s4_req_info = get_all_trans_in_mainpipe(waveform, 'l1', l2_i, start_time, end_time)
    
        node_L0_0 = f'L0_{l2_i^1}'
        node_L0_1 = f'L0_{l2_i}'
        node_L1_0 = f'L1_{l2_i^1}'
        node_L1_1 = f'L1_{l2_i}'
        node_L2_0 = f'L2_{l2_i^1}'
        node_L2_1 = f'L2_{l2_i}'
        normal_edges = [(node_L0_1, node_L1_1)]
        waiting_edges = [(node_L0_0, node_L1_0), (node_L1_0, node_L2_0), (node_L2_0, 'L3'),
                         ('L3', node_L2_1), (node_L2_1, node_L1_1)]
        blocked_edges = [(node_L1_1, node_L2_1), (node_L2_1, 'L3')]
        
        # graph_wrapper(normal_edges, waiting_edges, blocked_edges)
    
    
print('Stagnation Detected:')

print(f'No. of CoupledL2 - l2_i: {l2_i}\n'
      f'No. of L2 MSHR - mshr: {mshr}\n'
      f'Start Time - mshr_t: {mshr_t}ns\n')

# L2 MSHR内的请求信息
req_set = waveform.get_signal_from_path(f'VerifyTop.{cpl2_str}.slices_0.mshrCtl.mshrs_{mshr}.req_set').value_at_time(mshr_t)
req_tag = waveform.get_signal_from_path(f'VerifyTop.{cpl2_str}.slices_0.mshrCtl.mshrs_{mshr}.req_tag').value_at_time(mshr_t)
req_source = waveform.get_signal_from_path(f'VerifyTop.{cpl2_str}.slices_0.mshrCtl.mshrs_{mshr}.req_sourceId').value_at_time(mshr_t)
req_channel = waveform.get_signal_from_path(f'VerifyTop.{cpl2_str}.slices_0.mshrCtl.mshrs_{mshr}.req_channel').value_at_time(mshr_t)
req_opcode = waveform.get_signal_from_path(f'VerifyTop.{cpl2_str}.slices_0.mshrCtl.mshrs_{mshr}.req_opcode').value_at_time(mshr_t)

print(f'Request in L2 MSHR:\n'
      f'req_set: {req_set}\n'
      f'req_tag: {req_tag}\n'
      f'req_source: {req_source}\n'
      f'req_channel: {req_channel}\n'
      f'req_opcode: {req_opcode}\n'
      f'req_addr: {get_l2_addr(req_tag, req_set)}')

l3_mshr_i = -1
l3_mshr_start = -1
l3_mshr_end = -1

# 若请求为AcquireBlock
if (req_opcode, req_channel) == TileLinkConsts.AcquireBlock:
    print('Processing AcquireBlock\n')
    l3_mshr_i, l3_mshr_start, l3_mshr_end = acquire_block(waveform, l2_i, req_tag, req_set, mshr_t)
    if l3_mshr_end == -1:
        l3_mshr_end = length_ns

    
l3_send_trans = get_transactions(waveform, TileLinkConsts.l3_state_s_signals, 'VerifyTop.l3.slices_0.ms', l3_mshr_i, l3_mshr_start, l3_mshr_end)
l3_wait_trans = get_transactions(waveform, TileLinkConsts.l3_state_w_signals, 'VerifyTop.l3.slices_0.ms', l3_mshr_i, l3_mshr_start, l3_mshr_end)

print('L3 signals:')
for trans, t in l3_send_trans.items():
    print(f's_transaction {trans}: starting from {t[0]}ns to {t[1]}ns')
for trans, t in l3_wait_trans.items():
    print(f'w_transaction {trans}: starting from {t[0]}ns to {t[1]}ns')

# L3 发送了probe但超过500拍没收到probeack
if 's_probe' in l3_send_trans:
    if 'w_probeack' in l3_wait_trans:
        if l3_send_trans['s_probe'][1] + 500*ns_per_beat < l3_wait_trans['w_probeack'][1] or \
            l3_wait_trans['w_probeack'][1] == length_ns:
            print(f'L3 sent a Probe request to L2_{l2_i^1} but did not receive ProbeAck')
            probe_ack(waveform, l2_i ^ 1, get_l2_addr(req_tag, req_set), l3_send_trans['s_probe'][1], length_ns)