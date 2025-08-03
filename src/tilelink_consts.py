from math import log2
from param_configs import get_level_str


class TileLinkConsts:
    #                                 A    B    C    D    E
    PutFullData    = (0, 1)     #     .    .                   => AccessAck
    PutPartialData = (1, 1)     #     .    .                   => AccessAck
    ArithmeticData = (2, 1)     #     .    .                   => AccessAckData
    LogicalData    = (3, 1)     #     .    .                   => AccessAckData
    Get            = (4, 1)     #     .    .                   => AccessAckData
    Hint           = (5, 1)     #     .    .                   => HintAck
    AcquireBlock   = (6, 1)     #     .                        => Grant[Data]
    AcquirePerm    = (7, 1)     #     .                        => Grant[Data]
    Probe          = (6, 2)     #          .                   => ProbeAck[Data]
    AccessAck      = (0, 3)     #               .    .
    AccessAckData  = (1, 3)     #               .    .
    HintAck        = (2, 3)     #               .    .
    ProbeAck       = (4, 3)     #               .
    ProbeAckData   = (5, 3)     #               .
    Release        = (6, 3)     #               .              => ReleaseAck
    ReleaseData    = (7, 3)     #               .              => ReleaseAck
    Grant          = (4, 4)     #                    .         => GrantAck
    GrantData      = (5, 4)     #                    .         => GrantAck
    ReleaseAck     = (6, 4)     #                    .
    GrantAck       = (0, 5)     #                         .

    channel_bits = {
        'A': ['address', 'param', 'size', 'mask', 'opcode', 'data', 'source'],
        'B': ['address', 'param', 'data', 'source'],
        'C': ['address', 'param', 'data', 'source', 'opcode', 'size'],
        'D': ['opcode', 'param', 'size', 'source', 'sink'],
        'E': ['sink']
    }
    
    l2_state_s_signals = [
        'state_s_acquire',
        'state_s_pprobe',
        'state_s_rprobe',
        'state_s_probeack',
        'state_s_refill',
        'state_s_release'
    ]

    l2_state_w_signals = [
        'state_w_grantfirst',
        'state_w_grantlast',
        'state_w_pprobeack',
        'state_w_releaseack',
        'state_w_pprobeacklast',
        'state_w_rprobeacklast',
        'state_w_replResp'
    ]

    l3_state_s_signals = [
        's_acquire',
        's_execute',
        's_grantack',
        's_probe',
        's_probeack',
        's_release',
        's_transferput',
        's_wbclientsdir',
        's_wbclientstag',
        's_wbselfdir',
        's_wbselftag',
        's_writeprobe',
        's_writerelease'
    ]

    l3_state_w_signals = [
        'w_grant',
        'w_grantack',
        'w_grantfirst',
        'w_grantlast',
        'w_probeack',
        'w_probeackfirst',
        'w_probeacklast',
        'w_putwritten',
        'w_releaseack',
        'w_sinkack'
    ]

def OH2Int(oh):
    return int(log2(oh))

def Int2OH(i):
    return 1<<i



# signal_strs \in [l2_state_s_signals, l2_state_w_signals, l3_state_s_signals, l3_state_w_signals]
# mshr_i从start_time开始到end_time结束，返回所有事务作为字典，key为信号名，value为事务[start_time, end_time]
# 事务低电平为等待，高电平为完成
def get_transactions(waveform, signal_strs, sig_prefix, mshr_i, start_time, end_time):
    transactions = {sig: [] for sig in signal_strs}
    for sig in signal_strs:
        try:
            waveform_sig = waveform.get_signal_from_path(f'{sig_prefix}_{mshr_i}.{sig}')
        except RuntimeError:
            continue
        sig_changes = list(waveform_sig.all_changes())
        found = False
        flag = False
        last_v = 0
        for t, v in sig_changes:
            if t < start_time:
                last_v = v
                continue
            if t > end_time:
                if not found and last_v == 0:
                    transactions[sig].append([start_time, end_time])                
                break
            if v == 0:
                transactions[sig].append([t, -1])
                found = True
                flag = False
            elif found:
                transactions[sig][-1][1] = t
                flag = True
        
        if not found and last_v == 0:
            transactions[sig].append([start_time, end_time])  
        if found and not flag:
            transactions[sig][-1][1] = end_time
    return transactions


level_trans = {
    'l2': {
        's_sig': TileLinkConsts.l2_state_s_signals, 
        'w_sig': TileLinkConsts.l2_state_w_signals, 
        'prefix': lambda i: f'VerifyTop.{get_level_str('l2', i)}.slices_0.mshrCtl.mshrs'
    },
    'l3': {
        's_sig': TileLinkConsts.l3_state_s_signals, 
        'w_sig': TileLinkConsts.l3_state_w_signals, 
        'prefix': lambda _: 'VerifyTop.l3.slices_0.ms'
    }
}

def get_level(level, i):
    if level == 'l2':
        return get_level_str(level, i)
    else:
        return 'l3'
    
def print_transactions(waveform, level, l_i, mshr_i, start_time, end_time):
    send_trans = get_transactions(waveform, 
                                  level_trans[level]['s_sig'], 
                                  level_trans[level]['prefix'](l_i), 
                                  mshr_i, 
                                  start_time, 
                                  end_time)
    wait_trans = get_transactions(waveform, 
                                  level_trans[level]['w_sig'], 
                                  level_trans[level]['prefix'](l_i), 
                                  mshr_i, 
                                  start_time, 
                                  end_time)
    
    print(f'{get_level(level, l_i)} signals (during this request):')
    for trans, t_list in send_trans.items():
        if not t_list:
            continue
        print(f's_transaction {trans}: ', end='')
        for t in t_list[:5]:
            print(f'({t[0]}ns ~ {t[1]}ns)', end=' ')
        if len(t_list) <= 5:
            print('')
        else:
            print(f'... ({len(t_list)} in total)')
    for trans, t_list in wait_trans.items():
        if not t_list:
            continue
        print(f's_transaction {trans}: ', end='')
        for t in t_list[:5]:
            print(f'({t[0]}ns ~ {t[1]}ns)', end=' ')
        if len(t_list) <= 5:
            print('')
        else:
            print(f'... ({len(t_list)} in total)')
    
    return send_trans, wait_trans